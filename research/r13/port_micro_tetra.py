"""Run original STREAM/TETRA on an explicit R13 micro-DFG projection.

The unary algebra and fixed computation locations match one R13 plan. Upstream
IO is deliberately marked as a single-offchip whole-transfer projection: the
result is a real candidate seed, not an admitted R13 hardware-model baseline.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

R13 = Path(__file__).resolve().parent
SOURCE = R13.parent / "r12/deps/stream"
sys.path.insert(0, str(SOURCE))

from export_tetra import Capture, git, plain, require, sha
from model_builder import HARDWARE, small_plan_space, route, coord, physical_channel, micro_graph


@dataclass(frozen=True)
class CapacityBackend:
    """Only physical capacity/bandwidth input, not a second compute simulator."""
    capacity_bits: int
    bandwidth_bits: int

    def get_memory_capacity(self):
        return self.capacity_bits

    def get_max_memory_bandwidth(self):
        return self.bandwidth_bits

    def get_ir(self):
        return {"capacity_bits": self.capacity_bits, "bandwidth_bits": self.bandwidth_bits}


@dataclass(frozen=True)
class ResourceEnd:
    id: int
    name: str
    type: str = "resource_endpoint"
    col_id: int | None = None
    row_id: int | None = None

    def __str__(self):
        return self.name


def tensor_role(tr):
    stem, name = tr.inputs[0].name.split("/", 1)
    if name.startswith("input"):
        return stem, "load"
    if name.startswith("doubled"):
        return stem, "peer"
    if name.startswith("output"):
        return stem, "output"
    raise ValueError(f"unregistered transfer {tr.name}")


class R13PhysicalPaths:
    """Legal fixed-NoC candidates with shared physical service identities."""
    def __init__(self, accelerator, plan):
        self.accelerator = accelerator
        self.plan = plan
        self.resources = {}
        self.ends = {}
        self.records = []
        # Preserve all forwarding edges of both full physical toruses.
        for noc in (0, 1):
            delta = 1 if noc == 0 else -1
            for x in range(10):
                for y in range(12):
                    for axis in (0, 1):
                        b = [x, y]
                        b[axis] = (b[axis] + delta) % (10, 12)[axis]
                        self.resource(f"link/{noc}/r({x},{y})->r({coord(b)})", 256, "directed_router_link")
        for group in range(6):
            for channel in (0, 1):
                self.resource(f"dram/{group}/{channel}", 144, "shared_physical_dram_channel")

    def end(self, name):
        if name not in self.ends:
            self.ends[name] = ResourceEnd(len(self.ends), name)
        return self.ends[name]

    def resource(self, name, bandwidth, kind):
        from stream.hardware.architecture.noc.communication_link import CommunicationLink
        if name not in self.resources:
            # Self endpoint denotes one named service resource, never an extra route hop.
            obj = CommunicationLink(self.end(name+"/in"), self.end(name+"/out"), bandwidth, 0)
            self.resources[name] = {"object": obj, "kind": kind, "bandwidth_bits_per_cycle": bandwidth}
        return self.resources[name]["object"]

    def network_names(self, src, dst, noc):
        names = [f"link/{noc}/niu({coord(src)})->r({coord(src)})"]
        names += [f"link/{noc}/r({coord(a)})->r({coord(b)})" for a,b,_,_ in route(src,dst,noc)]
        names += [f"link/{noc}/r({coord(dst)})->niu({coord(dst)})"]
        for name in names:
            self.resource(name,256,"directed_network_link")
        return names

    def make(self, tr, src_core, dst_core):
        from stream.cost_model.communication_manager import MulticastPathPlan
        stem, role = tensor_role(tr)
        chain, epoch = int(stem[1]), int(stem[3])
        input_endpoint = [0,0] if chain == 0 else ([0,5] if self.plan["placement"]=="separate_group" else [0,1])
        offset = 2**30 if chain == 1 and self.plan["placement"]=="same_group_other_channel" else 0
        if role == "load":
            src, dst, noc = input_endpoint, self.plan["producers"][chain], self.plan["nocs"][0]
            address = offset+chain*0x10000+epoch*0x1000
            channel = physical_channel(src,address,1024)
            source_blocks = [f"dram/{channel[0]}/{channel[1]}/{(address%2**30)//16+i}" for i in range(64)]
            target_blocks = [f"l1/{coord(dst)}/{0x10000//16+i}" for i in range(64)]
        elif role == "peer":
            src,dst,noc = self.plan["producers"][chain],self.plan["consumers"][chain],self.plan["nocs"][1]
            channel = None
            source_blocks = [f"l1/{coord(src)}/{0x10000//16+i}" for i in range(64)]
            target_blocks = [f"l1/{coord(dst)}/{0x20000//16+i}" for i in range(64)]
        else:
            src,dst,noc = self.plan["consumers"][chain],[0,5],self.plan["nocs"][2]
            channel = (1,0)
            address = 0x100000+(chain*2+epoch)*0x1000
            source_blocks = [f"l1/{coord(src)}/{0x30000//16+i}" for i in range(64)]
            target_blocks = [f"dram/1/0/{address//16+i}" for i in range(64)]
        network = self.network_names(src,dst,noc)
        names = list(network)
        if channel is not None:
            names.append(f"dram/{channel[0]}/{channel[1]}")
        for c, direction, is_dram in ((src,"read",role=="load"),(dst,"write",role=="output")):
            if not is_dram:
                name=f"l1_port/{coord(c)}/noc{noc}/{direction}"
                self.resource(name,192,"independent_noc_l1_interface")
                names.append(name)
        path=MulticastPathPlan((src_core,),(dst_core,),len(network),tuple(self.resources[n]["object"] for n in names))
        require(tr.inputs[0].size_bits()==8192,"R13 micro payload differs")
        self.records.append({"path_object":path,"transfer":tr.name,"transaction":stem+"/"+role,
            "role":role,"payload_bytes":1024,"src":src,"dst":dst,"noc":noc,
            "source_channel":list(channel) if role=="load" else None,
            "destination_channel":list(channel) if role=="output" else None,
            "source_blocks":source_blocks,"target_blocks":target_blocks,
            "ordered_payload_links":network,"allocator_resource_names":names,
            "return_or_request_links":self.network_names(dst,src,noc),
            "control_cost_in_original_tetra":False})
        return path


def target_accelerator(plan):
    """Use public Core/Accelerator identities; bypass unused generic path search."""
    import networkx as nx
    from stream.hardware.architecture.accelerator import Accelerator, CoreGraph
    from stream.hardware.architecture.core import Core
    class R13Accelerator(Accelerator):
        def __init__(self, cores):
            graph=nx.DiGraph()
            graph.add_nodes_from(cores)
            self.name="R13_physical_io_and_directed_path_input_adapter"
            self.cores=CoreGraph(graph)
            self.offchip_core_id=4  # legacy metadata; all IO resolves through explicit bindings
            self.nb_shared_mem_groups=len(cores)
            self.communication_manager=None  # R13Scheduler supplies exact legal choices
    cores=[]
    for i,c in enumerate(HARDWARE["active_tiles_4"]):
        cores.append(Core(core_id=i,name=f"compute_{coord(c)}",core_type="r13.compute",
            backend=CapacityBackend((1499136-65536)*8,192),col_id=c[0],row_id=c[1]))
    for g in range(6):
        for ch in range(2):
            c=HARDWARE["dram_groups"][g][0]
            cores.append(Core(core_id=4+g*2+ch,name=f"dram_{g}_{ch}",core_type="r13.offchip",
                backend=CapacityBackend(2**30*8,144),col_id=c[0],row_id=c[1]))
    accelerator=R13Accelerator(cores)
    accelerator.io_bindings={}
    for chain in range(2):
        group = 1 if chain==1 and plan["placement"]=="separate_group" else 0
        channel = 1 if chain==1 and plan["placement"]=="same_group_other_channel" else 0
        for epoch in range(2):
            accelerator.io_bindings[f"c{chain}e{epoch}/load_source"]=accelerator.get_core(4+group*2+channel)
            accelerator.io_bindings[f"c{chain}e{epoch}/output_sink"]=accelerator.get_core(6)
    accelerator.physical_paths=R13PhysicalPaths(accelerator,plan)
    return accelerator


@contextmanager
def target_scheduler_class():
    """Change only the explicit IO/path input seam; original run/solve inherited."""
    from stream.cost_model import steady_state_scheduler as scheduler_module
    from stream.opt.allocation.constraint_optimization.transfer_and_tensor_allocation import TransferAndTensorAllocator
    from stream.workload.node import InEdge, OutEdge
    class R13Allocator(TransferAndTensorAllocator):
        def _retrieve_core_allocation(self,node):
            if isinstance(node,(InEdge,OutEdge)):
                return ((self.accelerator.io_bindings[node.name],),)
            return super()._retrieve_core_allocation(node)
    class R13Scheduler(scheduler_module.SteadyStateScheduler):
        def _retrieve_core_allocation(self,node):
            if isinstance(node,(InEdge,OutEdge)):
                return ((self.accelerator.io_bindings[node.name],),)
            return super()._retrieve_core_allocation(node)
        def determine_possible_memory_allocations(self,node,src,dsts):
            if len(dsts)==1 and isinstance(dsts[0],OutEdge):
                return self._retrieve_core_allocation(dsts[0])
            return super().determine_possible_memory_allocations(node,src,dsts)
        def update_mapping_for_transfer(self,node,src,dsts):
            self.r13_current_transfer=node
            try:
                return super().update_mapping_for_transfer(node,src,dsts)
            finally:
                self.r13_current_transfer=None
        def determine_possible_transfer_plans(self,src,possible_dst_allocs):
            sources=self._retrieve_core_allocation(src)
            require(len(sources)==len(possible_dst_allocs)==1,"fixed-placement intake only")
            require(len(sources[0])==len(possible_dst_allocs[0])==1,"unicast intake only")
            return (self.accelerator.physical_paths.make(self.r13_current_transfer,sources[0][0],possible_dst_allocs[0][0]),)
    old=scheduler_module.TransferAndTensorAllocator
    scheduler_module.TransferAndTensorAllocator=R13Allocator
    try:
        yield R13Scheduler
    finally:
        scheduler_module.TransferAndTensorAllocator=old


def write_inputs(folder, plan):
    import yaml
    folder.mkdir(parents=True, exist_ok=True)
    # Full ZigZag memory backend is just the declared aggregate tensor capacity.
    # No ZigZag cost estimation is run: explicit R13 compute service is supplied.
    core_source = SOURCE / "stream/inputs/examples/hardware/cores/tpu_like.yaml"
    core = yaml.safe_load(core_source.read_text(encoding="utf-8"))
    core["name"] = "r13_micro_capacity_projection"
    top = core["memories"]["sram_2MB"]
    top["size"] = (HARDWARE["public_fixed"]["l1_bytes_per_tile"] - 65536) * 8
    core["memories"] = {"l1_payload": top}
    (folder / "compute.yaml").write_text(yaml.safe_dump(core, sort_keys=False), encoding="utf-8")
    offchip_source = SOURCE / "stream/inputs/examples/hardware/cores/offchip.yaml"
    (folder / "offchip.yaml").write_bytes(offchip_source.read_bytes())
    hardware = {
        "name": "r13_micro_single_offchip_candidate_projection",
        "cores": {**{i: "./compute.yaml" for i in range(4)}, 4: "./offchip.yaml"},
        "core_coordinates": {**{i: c for i, c in enumerate(HARDWARE["active_tiles_4"])}, 4: [0, 0]},
        "offchip_core_id": 4, "unit_energy_cost": 0,
        "core_connectivity": [{"type": "bus", "cores": [0, 1, 2, 3, 4], "bandwidth": 192}],
    }
    (folder / "hardware.yaml").write_text(yaml.safe_dump(hardware, sort_keys=False), encoding="utf-8")
    semantic = {
        "schema": "r13.micro-tetra-input.v1", "r13_plan": plan,
        "generations": 2, "payload_bytes_per_transfer": 1024,
        "tensor_shape": [64, 4], "dtype": "i32",
        "data": "each16B block is four equal i32 lanes; distinct values across blocks/chains/generations",
        "operators": {"R13TimesTwo": "each output lane = 2 * input lane", "R13PlusThree": "each output lane = input lane + 3"},
        "compute_cost": {"latency_cycles": 64, "origin": "registered 32 / nominal eta_c=0.5, arithmetic only", "not_F": True},
        "capacity": {"payload_bytes_per_compute_tile": top["size"] // 8},
        "projection_losses": ["one aggregate offchip Core for every InEdge/OutEdge",
            "one shared192-bit/cycle surrogate transfer bus; no target routing or channel semantics",
            "whole tensors and whole-transfer slots, not source/receive address lifetimes",
            "two generations unrolled; source-last-read release and token reuse require later F lowering"],
        "input_source_hashes": {"hardware_model.json": sha(R13 / "hardware_model.json"),
                                "compute_backend_yaml": sha(core_source), "offchip_backend_yaml": sha(offchip_source)},
    }
    (folder / "semantics.json").write_text(json.dumps(semantic, indent=2) + "\n", encoding="utf-8")
    return semantic


def source_graph(accelerator, plan):
    from xdsl.dialects.builtin import i32
    from xdsl.ir.affine import AffineMap
    from stream.workload.node import ComputationNode, InEdge, OutEdge
    from stream.workload.tensor import Tensor
    from stream.workload.workload import Workload
    from stream.mapping.mapping import Mapping, FusedGroup
    from stream.cost_model.core_cost_lut import CoreCostLUT
    from stream.cost_model.core_cost import CoreCostEntry

    nodes = []
    computes = []
    assignment = {}
    coord_to_id = {tuple(c): i for i, c in enumerate(HARDWARE["active_tiles_4"])}
    for chain in range(2):
        for epoch in range(2):
            stem = f"c{chain}e{epoch}"
            incoming, doubled, output = [Tensor.create(f"{stem}/{suffix}", i32, (64, 4))
                                         for suffix in ("input", "doubled", "output")]
            producer = ComputationNode(name=stem+"/producer", inputs=(incoming,), outputs=(doubled,),
                operand_mapping=(AffineMap.identity(2), AffineMap.identity(2)), type="R13TimesTwo")
            consumer = ComputationNode(name=stem+"/consumer", inputs=(doubled,), outputs=(output,),
                operand_mapping=(AffineMap.identity(2), AffineMap.identity(2)), type="R13PlusThree")
            nodes += [InEdge(name=stem+"/load_source", outputs=(incoming,)), producer, consumer,
                      OutEdge(name=stem+"/output_sink", inputs=(output,))]
            computes += [producer, consumer]
            assignment[producer] = coord_to_id[tuple(plan["producers"][chain])]
            assignment[consumer] = coord_to_id[tuple(plan["consumers"][chain])]
    workload = Workload(nodes)
    mapping = Mapping(fused_groups=[FusedGroup("r13_micro", layers=tuple(n.name for n in computes))])
    costs = CoreCostLUT(load=False)
    for n in computes:
        core = accelerator.get_core(assignment[n])
        mapping.set_for_node(n, ((core,),), ((),))
        costs.add_cost(n, core, CoreCostEntry(energy_total=0, latency_total=64,
            ideal_cycle=32, ideal_temporal_cycle=32,
            metadata={"source": "R13 registered unary arithmetic service", "explicit_cost": True,
                      "energy_not_evaluated": True, "not_scalar_fallback": True}))
    return workload, mapping, costs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-index", type=int, default=0)
    parser.add_argument("--target", action="store_true", help="Use explicit physical IO/channel/directed-path input adapter")
    args = parser.parse_args()
    plans = small_plan_space()
    plan = plans[args.plan_index]
    suffix=plan["id"]+("_target" if args.target else "")
    folder = R13 / "inputs_micro" / suffix
    output = R13 / "artifacts" / f"tetra_micro_{suffix}.json"
    semantic = write_inputs(folder, plan)
    if args.target:
        semantic["projection_losses"]=["original whole-transfer cost/slots omit packet latency, control events and address lifetimes; F remains external"]
        semantic["hardware_adapter"]={"physical_dram_channel_cores":12,"compute_cores":4,
            "endpoint_aliases":"one capacity Core per physical channel, endpoint belongs to transfer route",
            "router_network":"all480 directed router links across two full10x12 toruses; no surrogate bus",
            "unused_hardware_yaml":"hardware.yaml documents earlier surrogate only; target run constructs public Core identities programmatically"}
        (folder/"semantics.json").write_text(json.dumps(semantic,indent=2)+"\n",encoding="utf-8")
    result = {"schema": "r13.tetra-micro-candidate.v1", "plan": plan, "input_semantics": semantic,
        "r13_p0_qualified": False, "fine_model_evaluated": False, "passed": False,
        "stream_commit": git("rev-parse", "HEAD"), "source_status_before": git("status", "--porcelain"),
        "producer_sha256": sha(__file__), "parsed_source_workloads": [], "groups": []}
    require(result["stream_commit"] == "75748cc17e7c43add5a7d0d8f080841eb26531c4", "wrong STREAM source")
    require(not result["source_status_before"], "source must be clean")
    capture = Capture(result)
    try:
        from stream.stages.context import StageContext
        from stream.stages.stage import LeafStage
        from stream.stages.parsing.accelerator_parser import AcceleratorParserStage
        from stream.cost_model.steady_state_scheduler import SteadyStateScheduler
        from stream.opt.solver import ConstraintSelection
        stage = AcceleratorParserStage([LeafStage], StageContext.from_kwargs(accelerator=str(folder / "hardware.yaml")))
        accelerator = target_accelerator(plan) if args.target else stage.parse_accelerator_from_yaml(str(folder / "hardware.yaml"))
        workload, mapping, costs = source_graph(accelerator, plan)
        result["parsed_source_workloads"] = [capture.workload(workload)]
        result["explicit_compute_costs"] = [{"node": n.name, "core_id": c.id, "entry": plain(costs.get_cost(n,c))}
                                            for n in costs.get_nodes() for c in costs.get_cores(n)]
        # Existing default IO methods demonstrably collapse distinct target domains.
        with (target_scheduler_class() if args.target else nullcontext(SteadyStateScheduler)) as Scheduler:
            scheduler = Scheduler(workload, accelerator, mapping, {}, costs, nb_cols_to_use=4,
                output_path=str(folder / "tetra_output"), backend="ORTOOLS_GSCIP", constraint_selection=ConstraintSelection())
            result["io_resolution"] = [{"node": n.name, "actual_core_ids": [[c.id for c in cs] for cs in scheduler._retrieve_core_allocation(n)]}
                for n in workload.nodes if type(n).__name__ in ("InEdge", "OutEdge")]
            started = time.perf_counter()
            with capture.hooks():
                scheduler.run()
        result["run_wall_seconds"] = time.perf_counter()-started
        result["groups"] = capture.groups
        result["analysis_latency_cycles"] = scheduler.latency_total
        result["last_phase_solve_stats"] = plain(scheduler.solve_stats)
        require(len(capture.groups)==1 and len(capture.groups[0]["allocators"])==1, "missing actual allocator")
        allocator=capture.groups[0]["allocators"][0]
        require(len(allocator["solve_phases"])==3, "missing solve phases")
        require(all(x["termination"]=="TerminationReason.OPTIMAL" for x in allocator["solve_phases"]), "nonoptimal phase")
        require(len(allocator["path_choices"])==12, "expected three transfers per chain and generation")
        if args.target:
            paths=accelerator.physical_paths
            result["physical_resources"]=[{"name":name,"object_id":capture.ids.of(item["object"],"link"),
                "kind":item["kind"],"bandwidth_bits_per_cycle":item["bandwidth_bits_per_cycle"]}
                for name,item in paths.resources.items()]
            result["physical_payloads"]=[{**{k:v for k,v in item.items() if k!="path_object"},
                "path_id":capture.ids.of(item["path_object"],"path")} for item in paths.records]
            reference=micro_graph(plan)["metadata"]
            data_packets={p["id"]:p for p in reference["packets"] if p["payload_bytes"]==1024}
            require(len(data_packets)==12,"reference payload count differs")
            for item in result["physical_payloads"]:
                pid=item["transaction"]+("/response" if item["role"]=="load" else "/data")
                packet=data_packets[pid]
                for key in ("src","dst","noc","payload_bytes"):
                    require(item[key]==packet[key],f"payload {pid} {key} mismatch")
                require(item["ordered_payload_links"]==packet["links"],f"route mismatch {pid}")
                tags=reference["tags"]
                srcblocks=[b for op in packet["read_ops"] for b in tags[op]["blocks"]]
                dstblocks=[b for op in packet["write_ops"] for b in tags[op]["blocks"]]
                require(item["source_blocks"]==srcblocks and item["target_blocks"]==dstblocks,f"block mismatch {pid}")
            result["physical_input_checks"]={"passed":True,"payload_transfers_checked":12,
                "exact_source_target_blocks_checked":1536,"all_directed_payload_routes_match_micro_graph":True,
                "physical_dram_channels":12,"full_network_router_links":480,"surrogate_bus_used":False,
                "completion_and_control_semantics_qualified":False,"window_refinement_completed":False}
        result["passed"] = True
        result["interpretation"] = ("real TETRA with explicit physical IO/channel/directed-path input adaptation; F lifecycle/control/window qualification remains open"
            if args.target else "real original TETRA candidate for same unary DFG/fixed compute locations; target IO/path/lifetime projection is not qualified")
    except Exception as exc:
        result["groups"] = capture.groups
        result["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finally:
        result["source_status_after"] = git("status", "--porcelain")
        if result["source_status_after"] != result["source_status_before"]:
            result["passed"] = False
            result["source_mutation_detected"] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":result["passed"],"artifact":str(output),"error":result.get("error",{}).get("message")},ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
