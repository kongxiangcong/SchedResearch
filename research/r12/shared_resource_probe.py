"""Reproduce a shared-bus conservation violation in pinned STREAM path costing.

Uses real upstream Tensor/TransferNode/Core/Accelerator/MulticastPathPlan types.
No upstream edits, kernel timings, corrected optimizer run, or Wormhole claim.
"""

from __future__ import annotations

import hashlib
import json
from math import ceil
from pathlib import Path
import subprocess


R12 = Path(__file__).resolve().parent
STREAM = R12 / "deps/stream"
COMMIT = "75748cc17e7c43add5a7d0d8f080841eb26531c4"
BITS = 262144
BANDWIDTH = 128


def check(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(STREAM), *args], text=True).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    check(git("rev-parse", "HEAD") == COMMIT, "Unexpected STREAM revision")
    before = git("status", "--porcelain")
    import yaml
    from xdsl.dialects.builtin import i16
    from xdsl.ir.affine import AffineMap
    from stream.cost_model.communication_manager import MulticastPathPlan
    from stream.hardware.architecture.accelerator import Accelerator
    from stream.hardware.architecture.core import Core
    from stream.hardware.architecture.noc.communication_link import CommunicationLink
    from stream.opt.allocation.constraint_optimization import utils
    from stream.parser.accelerator_factory import AcceleratorFactory
    from stream.workload.node import TransferNode, TransferType
    from stream.workload.tensor import Tensor

    check(Path(utils.__file__).resolve().is_relative_to(STREAM), "Wrong STREAM import")
    tensor = Tensor.create("partitioned_input", i16, (1, 16, 32, 32))
    output = Tensor.create("replicated_output", i16, (1, 16, 32, 32))
    transfer = TransferNode(
        name="shared_resource_probe", inputs=(tensor,), outputs=(output,),
        operand_mapping=(AffineMap.identity(4), AffineMap.identity(4)),
        transfer_type=TransferType.COMPUTE_TO_COMPUTE,
    )
    check(tensor.size_bits() == BITS, "Unexpected source bits")

    def shared_case(source_ids: list[int], target_ids: list[int], name: str) -> dict:
        ids = set(source_ids + target_ids)
        cores = [Core(core_id=i, name=f"c{i}", core_type="zigzag.compute") for i in range(max(ids) + 1)]
        graph = AcceleratorFactory({"core_connectivity": [{
            "type": "bus", "cores": list(range(len(cores))), "bandwidth": BANDWIDTH,
        }]}).create_core_graph(cores)
        accelerator = Accelerator(name, graph, nb_shared_mem_groups=len(cores))
        source = tuple(cores[i] for i in source_ids)
        target = tuple(cores[i] for i in target_ids)
        plans = accelerator.communication_manager.get_possible_transfer_plan(source, target)
        unique_bus_objects = {id(d["cl"]) for _, _, d in graph.edges(data=True)}
        check(len(unique_bus_objects) == 1, "Factory created multiple physical bus objects")
        check(all(len(p.links_used) == 1 for p in plans), "Unexpected plan resources")
        cycles = sorted({utils.get_transfer_latency_for_path(transfer, p) for p in plans})
        check(len(cycles) == 1, "Equivalent shared-bus paths differ in cost")
        return {
            "name": name, "sources": source_ids, "targets": target_ids,
            "path_origin": "upstream AcceleratorFactory and CommunicationManager",
            "tensor_bits": BITS, "global_bus_bits_per_cycle": BANDWIDTH,
            "distinct_bus_objects": 1, "links_per_plan": 1,
            "plan_count": len(plans), "upstream_path_cycles": cycles[0],
            "optimistic_broadcast_conservation_cycles": ceil(BITS / BANDWIDTH),
            "below_optimistic_conservation": cycles[0] < ceil(BITS / BANDWIDTH),
            "conservation_assumption": "every distinct source-owned bit is needed remotely; perfect broadcast allowed, no compression/recomputation/free extra copies",
        }

    cases = [
        shared_case([0], [1, 2, 3, 4], "one_to_four_broadcast_control"),
        shared_case([0, 1, 2, 3], [4], "four_to_one_gather_control"),
        shared_case([0, 1], [0, 1], "two_core_shards_to_replicas"),
        shared_case([0, 1, 2, 3], [0, 1, 2, 3], "four_core_shards_to_replicas"),
        shared_case([0, 1, 2, 3], [4, 5, 6, 7], "four_sources_four_distinct_targets_shared_bus"),
    ]
    check([c["upstream_path_cycles"] for c in cases] == [2048, 2048, 1024, 512, 512], "Unexpected upstream behavior")

    # Positive control for the helper's stated one-to-one disjoint-chain contract.
    # This explicit plan is not claimed to come from the all-pairs path generator.
    cores = [Core(core_id=i, name=f"d{i}", core_type="zigzag.compute") for i in range(8)]
    links = tuple(CommunicationLink(cores[i], cores[i + 4], BANDWIDTH, 0) for i in range(4))
    disjoint = MulticastPathPlan(tuple(cores[:4]), tuple(cores[4:]), 4, links)
    disjoint_cycles = utils.get_transfer_latency_for_path(transfer, disjoint)
    check(disjoint_cycles == ceil((BITS // 4) / BANDWIDTH), "Disjoint-chain control changed")

    # Word-identity ledger is independent of the upstream latency helper. Every
    # one of the 16384 words is initially owned by exactly one source; each of
    # the other three destinations needs it. Even perfect bus multicast must
    # inject each distinct word at least once.
    words = BITS // 16
    owners = [set(range(k * words // 4, (k + 1) * words // 4)) for k in range(4)]
    all_words = set(range(words))
    remote_demands = [all_words - owned for owned in owners]
    must_cross = set.union(*remote_demands)
    check(len(must_cross) == words, "Remote-demand conservation incorrect")

    # Read the already-executed official fixture; do not rerun or modify it.
    smoke_dir = R12 / "results/baseline_smoke"
    result_path = smoke_dir / "result.json"
    ir_path = smoke_dir / "allocation_ir.json"
    slots_path = smoke_dir / "pipeline/upstream-2conv/group_0/tetra/slot_latency_breakdown.yaml"
    smoke = json.loads(result_path.read_text(encoding="utf-8"))
    ir = json.loads(ir_path.read_text(encoding="utf-8"))
    breakdown = yaml.safe_load(slots_path.read_text(encoding="utf-8"))
    selected = [p for p in smoke["chosen_transfer_paths"] if p["transfer"] == "Transfer(conv1_out)"]
    check(len(selected) == 1, "Expected one chosen conv1_out transfer")
    check(selected[0]["sources"] == selected[0]["targets"] == list(range(4)), "Fixture placement changed")
    check(selected[0]["tensor_bits"] == BITS, "Fixture tensor size changed")
    check(selected[0]["link_resources"] == ["CL(Any, Any, bw=128)"], "Fixture path changed")
    occurrences = [
        {"slot": slot["slot"], "slot_latency_cycles": slot["slot_latency_cycles"], "contributor": contributor}
        for slot in breakdown["slots"] for contributor in slot["transfer_contributors"]
        if contributor["name"] == "Transfer(conv1_out)"
    ]
    check(len(occurrences) == 1 and occurrences[0]["slot_latency_cycles"] == 512, "Fixture has an extra charge")
    check(occurrences[0]["contributor"]["active_latency_absent_loops"] == 512, "Fixture rescales the transfer")
    check(smoke["iterations"] == 1 and ir["latency"]["overlap_between_iterations"] == 0, "Fixture repeats/overlaps")
    reuse = [x for x in breakdown["tensor_reuse"] if x["tensor"] in ("conv1_out", "conv1_out_1")]
    check(all(x["reuse_factor"] == 1 for x in reuse) and len(reuse) == 2, "Fixture reuse changed")
    source_target_storage = []
    for row in ir["performance"]["memory_occupancy"]:
        if row["core_id"] not in range(4):
            continue
        storage = {t["tensor"]: t["bits"] for t in row["tensors"]}
        check(storage["conv1_out"] == BITS // 4 and storage["conv1_out_1"] == BITS, "Fixture allocation footprints changed")
        source_target_storage.append({"core": row["core_id"], "source_bits": storage["conv1_out"], "target_bits": storage["conv1_out_1"]})
    total_slots = sum(x["slot_latency_cycles"] for x in breakdown["slots"])
    check(total_slots == ir["latency"]["total"] == 12808, "Fixture total contains an additional factor")

    paths = [
        "stream/opt/allocation/constraint_optimization/utils.py",
        "stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py",
        "stream/cost_model/communication_manager.py", "stream/cost_model/steady_state_scheduler.py",
        "stream/parser/accelerator_factory.py", "stream/hardware/architecture/noc/communication_link.py",
    ]
    after = git("status", "--porcelain")
    check(before == after, "Probe changed upstream checkout")
    affine_path = R12 / "artifacts/shared_resource_affine_audit.json"
    affine = json.loads(affine_path.read_text(encoding="utf-8"))
    check(affine["status"] == "earlier_full_allgather_demand_inference_refuted", "Missing independent fixture demand correction")
    return {
        "schema": "r12.shared-resource-probe.v1",
        "status": "parameterized_shared_bus_undercharge_confirmed_2conv_demand_inference_refuted",
        "stream_revision": COMMIT,
        "source_sha256": {p: digest(STREAM / p) for p in paths},
        "upstream_status_before": before, "upstream_status_after": after,
        "real_upstream_type_cases": cases,
        "disjoint_chain_positive_control": {
            "path_origin": "explicit upstream MulticastPathPlan with four separate equal-bandwidth links",
            "upstream_cycles": disjoint_cycles, "per_link_bits": BITS // 4,
            "independent_per_link_bound_cycles": 512,
        },
        "independent_four_core_conservation": {
            "logical_words": words, "bits_per_word": 16,
            "words_initially_owned_per_core": [len(s) for s in owners],
            "remote_words_required_per_core": [len(s) for s in remote_demands],
            "distinct_words_requiring_bus_service_even_with_perfect_broadcast": len(must_cross),
            "minimum_bus_payload_bits": len(must_cross) * 16,
            "minimum_bus_service_cycles": ceil(len(must_cross) * 16 / BANDWIDTH),
            "without_broadcast_remote_delivery_cycles": ceil(sum(map(len, remote_demands)) * 16 / BANDWIDTH),
        },
        "observed_existing_2conv_solve": {
            "evidence": "read existing solver artifacts; this probe did not reoptimize",
            "input_artifact_sha256": {str(p.relative_to(R12)): digest(p) for p in (result_path, ir_path, slots_path)},
            "chosen_path": selected[0], "matching_slot_entries": occurrences,
            "source_target_allocation_footprints_bits_not_consumer_demand": source_target_storage,
            "iterations": 1, "overlap_cycles": 0, "source_target_reuse": reuse,
            "sum_of_all_slot_cycles": total_slots,
            "same_fixed_plan_substitution_arithmetic": {
                "old_total": total_slots, "old_transfer_slot": 512,
                "conditional_full_payload_transfer_slot": 2048, "arithmetic_total": total_slots - 512 + 2048,
                "not_a_reoptimized_or_measured_result": True,
                "condition": "require the complete 262144-bit payload to cross the bus; this is not established as necessary for the actual spatially partitioned 2conv computation",
            },
        },
        "fixture_affine_correction": {
            "artifact": str(affine_path.relative_to(R12)), "sha256": digest(affine_path),
            "final_split_axis": "ox for both Conv1 and Conv2; not output channel",
            "aligned_halo_payload_bits": affine["halo_payload_bits"],
            "aligned_halo_bus_service_bound_cycles": 384,
            "original_512_below_this_bound": False,
            "complete_tensor_2048_not_a_fixture_necessity_proof": True,
        },
        "scope": {
            "upstream_files_modified": False, "full_solver_rerun": False,
            "native_hardware_measurement": False, "wormhole_bug_claim": False,
            "H1_performance_result": False, "novel_algorithm_claim": False,
            "claim": "under an explicitly required full-payload transfer contract, one shared 128-bit/cycle bus cannot carry 262144 bits in 512 cycles; the actual 2conv computation only establishes a 49152-bit aligned-halo demand witness",
        },
        "producer_sha256": digest(Path(__file__)),
    }


if __name__ == "__main__":
    result = run()
    destination = R12 / "artifacts/shared_resource_probe.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "full_payload_shared_bus_cycles": 512, "full_payload_conservation_cycles": 2048,
                      "actual_2conv_aligned_halo_bound": 384, "conditional_fixed_plan_arithmetic_only": 14344, "output": str(destination)}))
