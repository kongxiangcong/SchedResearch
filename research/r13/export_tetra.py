"""Observe one real pinned STREAM/TETRA run without changing its algorithm.

Run with the existing R12 Python environment. The only supported input in this
intake exporter is the official 2conv fixture; this is not a Wormhole P0 backend.
All observation hooks are process-local and restored in finally blocks.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
R13 = Path(__file__).resolve().parent
SOURCE = ROOT / "research/r12/deps/stream"
COMMIT = "75748cc17e7c43add5a7d0d8f080841eb26531c4"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(SOURCE), *args], text=True).strip()


def plain(value):
    """Lossless JSON for affine dataclasses, primitive parameters and enums."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Enum):
        return {"enum": type(value).__name__, "name": value.name}
    if is_dataclass(value):
        return {"type": type(value).__name__, **{f.name: plain(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if hasattr(value, "total_seconds"):
        return {"seconds": value.total_seconds()}
    raise TypeError(f"Unregistered JSON representation: {type(value).__name__}")


class Ids:
    """IDs preserve object identity, including distinct equal-looking links."""
    def __init__(self):
        self.objects = []
        self.by_id = {}

    def of(self, obj, kind):
        key = id(obj)
        if key not in self.by_id:
            self.by_id[key] = f"{kind}{len(self.objects)}"
            self.objects.append(obj)  # Keep references alive; Python cannot recycle IDs.
        return self.by_id[key]


class Capture:
    def __init__(self, result):
        self.result = result
        self.ids = Ids()
        self.groups = []
        self.active = []
        self.active_tta = []

    def tensor(self, tensor):
        sub = tensor.subview
        dynamic = len(sub.offsets) + len(sub.sizes) + len(sub.strides)
        require(dynamic == 0, f"Dynamic subview needs an explicit exporter: {tensor.name}")
        return {
            "id": self.ids.of(tensor, "tensor"), "name": tensor.name,
            "shape": list(tensor.shape), "dtype": str(tensor.operand_type),
            "bitwidth": tensor.operand_type.bitwidth, "footprint_bits": tensor.size_bits(),
            "subview": {
                "source_id": self.ids.of(sub.source, "ssa"),
                "source_type": str(sub.source.type), "result_type": str(sub.result.type),
                "static_offsets": list(sub.static_offsets.get_values()),
                "static_sizes": list(sub.static_sizes.get_values()),
                "static_strides": list(sub.static_strides.get_values()),
                "raw_ir": str(sub),
            },
        }

    def workload(self, workload):
        from stream.workload.node import HasIterationSpace
        nodes = []
        for node in workload.dataflow_sort():
            item = {"id": self.ids.of(node, "node"), "name": node.name, "type": type(node).__name__}
            item["inputs"] = [self.tensor(t) for t in getattr(node, "inputs", ())]
            item["outputs"] = [self.tensor(t) for t in getattr(node, "outputs", ())]
            if isinstance(node, HasIterationSpace):
                dims = workload.get_dims(node)
                item.update({
                    "local_dimension_order": [str(d) for d in dims],
                    "local_dimension_sizes": [workload.get_dimension_size(d) for d in dims],
                    "global_dim_indices": list(workload.global_idxs[node]),
                    "operand_affine_maps": [
                        {"tensor_id": self.ids.of(t, "tensor"), "text": str(m), "ast": plain(m)}
                        for t, m in zip(node.tensors, node.operand_mapping, strict=True)
                    ],
                })
            if hasattr(node, "type"):
                item["operator"] = str(node.type)
            if hasattr(node, "transfer_type"):
                item["transfer_type"] = str(node.transfer_type)
            nodes.append(item)
        return {
            "nodes": nodes,
            "edges": [{"source": self.ids.of(s, "node"), "target": self.ids.of(t, "node")} for s, t in workload.edges],
            "dimension_relations": [str(x) for x in workload.dimension_relations()],
        }

    def core(self, c):
        return {"object_id": self.ids.of(c, "core"), "core_id": c.id,
                "name": str(c), "type": c.type,
                "row_id": getattr(c, "row_id", None), "col_id": getattr(c, "col_id", None)}

    def endpoint(self, obj):
        return self.core(obj) if hasattr(obj, "id") else {"literal": obj}

    def link(self, link):
        return {"id": self.ids.of(link, "link"), "sender": self.endpoint(link.sender),
                "receiver": self.endpoint(link.receiver), "bandwidth_bits_per_cycle": link.bandwidth,
                "unit_energy_cost": link.unit_energy_cost, "bidirectional": link.bidirectional}

    def path(self, path):
        return {"id": self.ids.of(path, "path"),
                "sources": [self.core(c) for c in path.sources],
                "targets": [self.core(c) for c in path.targets],
                "total_hops_objective": path.total_hops_objective,
                "links": [self.link(c) for c in path.links_used],
                "ordered_packet_path_available": False, "noc_id": None}

    def mapping(self, mapping):
        from stream.cost_model.communication_manager import MulticastPathPlan
        entries = []
        for node, m in mapping.items():
            resources = []
            for item in m.resource_allocation:
                if isinstance(item, MulticastPathPlan):
                    resources.append({"path": self.path(item)})
                else:
                    resources.append({"cores": [self.core(c) for c in item]})
            entries.append({"node_id": self.ids.of(node, "node"), "node_name": node.name,
                            "resource_allocation": resources,
                            "inter_core_tiling": [[[str(d), n] for d, n in x] for x in m.inter_core_tiling],
                            "memory_allocation": [[self.core(c) for c in (cs if isinstance(cs, (tuple, list)) else (cs,))]
                                                  for cs in m.memory_allocation]})
        return {"nodes": entries,
                "fused_groups": [{"name": g.name, "layers": list(g.layers),
                                  "intra_core_tiling": [[str(d), n] for d, n in g.intra_core_tiling]}
                                 for g in mapping.fused_groups],
                "runtime_args": dict(mapping.runtime_args)}

    def allocator_before(self, tta):
        return {
            "workload": self.workload(tta.workload), "mapping_before_solve": self.mapping(tta.mapping),
            "iterations": tta.iterations,
            "multiplicities": [{"node_id": self.ids.of(n, "node"), "value": k} for n, k in tta.multiplicities.items()],
            "slot_of": [{"node_id": self.ids.of(n, "node"), "node_name": n.name, "slot": v} for n, v in tta.slot_of.items()],
            "tensor_choices": [{"tensor": self.tensor(t), "choices": [[self.core(c) for c in cs] for cs in choices]}
                               for t, choices in tta.possible_tensor_allocations.items()],
            "path_choices": [{"transfer_id": self.ids.of(t, "node"), "transfer_name": t.name,
                              "choices": [self.path(p) for p in ps]} for t, ps in tta.possible_transfer_allocations.items()],
            "ssis_order": "innermost_to_outermost",
            "ssis": [{"owner_id": self.ids.of(owner, "tensor" if type(owner).__name__ == "Tensor" else "node"),
                      "owner_name": owner.name, "owner_type": type(owner).__name__,
                      "variables": [{"dimension": str(v.dimension), "size": v.size, "type": v.type.name,
                                     "effect": v.effect.name, "reuse": v.reuse.name} for v in space.variables]}
                     for owner, space in tta.ssis.items()],
            "reuse_options": [{"tensor_id": self.ids.of(t, "tensor"), "stop_level": stop,
                               "reuse_factor": value, "tiles_needed": tta.tiles_needed_levels[(t, stop)],
                               "bds_needed": tta.bds_needed_levels[(t, stop)]} for (t, stop), value in tta.reuse_levels.items()],
            "constraint_selection": plain(tta.constraint_selection),
            "context": {"force_double_buffering": tta.force_double_buffering,
                        "offchip_core_id": tta.offchip_core_id,
                        "mem_cores": [self.core(c) for c in tta.mem_cores]},
            "solver_parameters": plain(tta.model._params),
            "lex_objectives": [{"name": o.name, "priority": o.priority,
                                "abs_tol": o.abs_tol, "rel_tol": o.rel_tol} for o in tta.model._lex_objectives],
            "solve_phases": [],
        }

    def allocator_after(self, tta, value):
        levels, depths, placements, paths, memories, latency, overlap, per_iteration = value
        return {
            "tensor_reuse_levels": [{"tensor_id": self.ids.of(t, "tensor"), "stop_level": x} for t, x in levels.items()],
            "tensor_depths": [{"tensor_id": self.ids.of(t, "tensor"), "depth": x} for t, x in depths.items()],
            "tensor_allocations": [{"tensor_id": self.ids.of(t, "tensor"), "cores": [self.core(c) for c in cs]} for t, cs in placements.items()],
            "transfer_allocations": [{"transfer_id": self.ids.of(t, "node"), "path": self.path(p)} for t, p in paths.items()],
            "memory_allocations": [{"transfer_id": self.ids.of(t, "node"), "cores": [self.core(c) for c in cs]} for t, cs in memories.items()],
            "analysis_latency_cycles": {"total": latency, "overlap": overlap, "per_iteration": per_iteration},
            "last_phase_solve_stats": plain(tta.model.solve_stats()),
        }

    @contextmanager
    def hooks(self):
        from stream.parser.onnx.model import ONNXModelParser
        from stream.cost_model.steady_state_scheduler import SteadyStateScheduler
        from stream.opt.allocation.constraint_optimization.transfer_and_tensor_allocation import TransferAndTensorAllocator
        from stream.opt.solver import solver as solver_module
        parser_run = ONNXModelParser.run
        scheduler_run = SteadyStateScheduler.run
        allocator_solve = TransferAndTensorAllocator.solve
        mathopt_solve = solver_module.mathopt.solve

        def observe_parser(parser, *args, **kwargs):
            result = parser_run(parser, *args, **kwargs)
            self.result["parsed_source_workloads"].append(self.workload(parser.workload))
            return result

        def observe_scheduler(scheduler, *args, **kwargs):
            group = {"group_index": len(self.groups), "source_workload": self.workload(scheduler.workload),
                     "mapping_before_schedule": self.mapping(scheduler.mapping), "allocators": []}
            self.groups.append(group)
            self.active.append(group)
            try:
                result = scheduler_run(scheduler, *args, **kwargs)
                group["final_workload"] = self.workload(scheduler.steady_state_workload)
                group["mapping_after_schedule"] = self.mapping(scheduler.mapping)
                return result
            finally:
                self.active.pop()

        def observe_allocator(tta, *args, **kwargs):
            require(bool(self.active), "Allocator executed outside observed scheduler")
            record = self.allocator_before(tta)
            self.active[-1]["allocators"].append(record)
            self.active_tta.append(record)
            try:
                result = allocator_solve(tta, *args, **kwargs)
                record["selected"] = self.allocator_after(tta, result)
                return result
            finally:
                self.active_tta.pop()

        def observe_mathopt(model, solver_type, *args, **kwargs):
            started = time.perf_counter()
            result = mathopt_solve(model, solver_type, *args, **kwargs)
            if self.active_tta:
                record = self.active_tta[-1]
                idx = len(record["solve_phases"])
                record["solve_phases"].append({
                    "phase_index": idx, "objective_definition": record["lex_objectives"][idx],
                    "solver_type": solver_type.name, "termination": str(result.termination.reason),
                    "termination_detail": result.termination.detail,
                    "primal_feasible": result.has_primal_feasible_solution(),
                    "objective": result.objective_value() if result.has_primal_feasible_solution() else None,
                    "best_objective_bound": plain(result.best_objective_bound()),
                    "solve_time_seconds": result.solve_stats.solve_time.total_seconds(),
                    "wrapper_wall_seconds": time.perf_counter() - started,
                    "effective_parameters_text": str(kwargs.get("params")),
                })
            return result

        ONNXModelParser.run = observe_parser
        SteadyStateScheduler.run = observe_scheduler
        TransferAndTensorAllocator.solve = observe_allocator
        solver_module.mathopt.solve = observe_mathopt
        try:
            yield
        finally:
            ONNXModelParser.run = parser_run
            SteadyStateScheduler.run = scheduler_run
            TransferAndTensorAllocator.solve = allocator_solve
            solver_module.mathopt.solve = mathopt_solve


def validate(result):
    require(result["parsed_source_workloads"], "No parsed source workload captured")
    require(result["groups"], "No scheduler captured")
    paths = phases = 0
    for group in result["groups"]:
        require(group["allocators"], "No live allocator captured")
        for a in group["allocators"]:
            require(a.get("selected"), "Allocator did not return a selected result")
            require(len(a["solve_phases"]) == len(a["lex_objectives"]) == 3, "Missing lexicographic phase")
            require(all(p["termination"] == "TerminationReason.OPTIMAL" for p in a["solve_phases"]), "Nonoptimal phase")
            selected = {x["transfer_id"]: x["path"]["id"] for x in a["selected"]["transfer_allocations"]}
            for entry in a["path_choices"]:
                require(selected[entry["transfer_id"]] in {p["id"] for p in entry["choices"]}, "Selected path was not an actual candidate")
                paths += len(entry["choices"])
            phases += len(a["solve_phases"])
            require(a["slot_of"] and a["ssis"] and a["tensor_choices"], "Missing candidate state")
    result["validation"] = {"passed": True, "groups": len(result["groups"]),
                            "path_candidates": paths, "solver_phases": phases,
                            "selected_paths_belong_to_original_candidates": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=R13 / "artifacts/tetra_export.json")
    parser.add_argument("--log-dir", type=Path, default=R13 / "logs/tetra_export")
    args = parser.parse_args()
    output, log_dir = args.output.resolve(), args.log_dir.resolve()
    require(output.is_relative_to(R13) and log_dir.is_relative_to(R13), "Outputs must stay inside R13")
    output.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(SOURCE))
    import stream.api as api
    from stream.opt.solver import ConstraintSelection
    from stream.plugins import loaded_overlays
    require(Path(api.__file__).resolve().is_relative_to(SOURCE), "Wrong editable import")
    require(git("rev-parse", "HEAD") == COMMIT, "Source commit differs")
    before = git("status", "--porcelain")
    require(not before, "Fixed source is dirty")
    hardware = SOURCE / "stream/inputs/examples/hardware/tpu_like_quad_core.yaml"
    workload = SOURCE / "stream/inputs/testing/workload/2conv_1_8_32_32_16_32_3.onnx"
    result = {
        "schema": "r13.tetra-live-candidate.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "official_2conv_upstream_analytical_candidate_export",
        "r13_p0_qualified": False, "hardware_model_evaluated": False,
        "unrepresented_target_features": ["Wormhole coordinates and legal dual NoC packet routes",
            "multiple physical DRAM channels and endpoint aliases", "source slice materialization",
            "source_last_read/target_visible/notification and release windows"],
        "provenance": {"stream_commit": COMMIT, "source_status_before": before,
            "python": sys.version, "executable": sys.executable, "api_path": str(Path(api.__file__).resolve()),
            "packages": {x: version(x) for x in ("stream-dse", "zigzag-dse", "ortools", "pydantic", "xdsl")},
            "hardware": {"path": str(hardware.relative_to(SOURCE)), "sha256": sha(hardware)},
            "workload": {"path": str(workload.relative_to(SOURCE)), "sha256": sha(workload)},
            "exporter_sha256": sha(__file__),
            "observer_policy": "call original functions unchanged; observe live objects and results; restore hooks in finally"},
        "parsed_source_workloads": [], "groups": [], "passed": False,
    }
    capture = Capture(result)
    previous_cwd = Path.cwd()
    try:
        os.chdir(SOURCE)
        api.configure_logging()
        started = time.perf_counter()
        with capture.hooks():
            context = api.optimize_allocation_co_generic(
                hardware=str(hardware), workload=str(workload), experiment_id="official-2conv-live-export",
                output_path=str(log_dir / "pipeline"), backend="ortools_gscip",
                constraint_selection=ConstraintSelection(), skip_if_exists=False,
            )
        result["pipeline_wall_seconds"] = time.perf_counter() - started
        result["groups"] = capture.groups
        result["analysis_total_latency_cycles"] = context.get("total_latency")
        result["loaded_overlays"] = plain(loaded_overlays())
        require(not result["loaded_overlays"], "Unexpected algorithm overlay")
        validate(result)
        result["passed"] = True
    except Exception as exc:
        result["groups"] = capture.groups
        result["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finally:
        os.chdir(previous_cwd)
        result["provenance"]["source_status_after"] = git("status", "--porcelain")
        if result["provenance"]["source_status_after"] != before:
            result["passed"] = False
            result["source_mutation_detected"] = True
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "artifact": str(output),
                      "validation": result.get("validation"), "error": result.get("error", {}).get("message")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
