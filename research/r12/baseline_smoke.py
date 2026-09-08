"""Qualify the pinned STREAM install with a real TETRA solve.

This runs the upstream two-convolution analytical fixture. It is neither a
Wormhole backend nor a correctness/performance acceptance test for R12 P0.
Run with the R12 virtual environment; all outputs stay in the supplied folder.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


STREAM_COMMIT = "75748cc17e7c43add5a7d0d8f080841eb26531c4"
R12 = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(source), *args], text=True, encoding="utf-8"
    ).strip()


def run(source: Path, output: Path, result: dict) -> None:
    check(git(source, "rev-parse", "HEAD") == STREAM_COMMIT, "STREAM HEAD differs from the contract")
    result["stream_commit"] = STREAM_COMMIT
    result["stream_status_before"] = git(source, "status", "--porcelain")
    result["python"] = sys.version
    result["executable"] = sys.executable
    result["packages"] = {
        name: version(name)
        for name in ("stream-dse", "zigzag-dse", "ortools", "pydantic", "xdsl", "numpy", "onnx")
    }

    import stream.api as stream_api
    from stream.cost_model.communication_manager import MulticastPathPlan
    from stream.ir.allocation import AllocationIR
    from stream.opt.allocation.constraint_optimization.utils import get_transfer_latency_for_path
    from stream.opt.solver import ConstraintSelection, SolverBackend, SolverVarType, create_solver

    api_path = Path(stream_api.__file__).resolve()
    check(api_path.is_relative_to(source), f"Wrong editable import: {api_path}")
    result["stream_api_path"] = str(api_path)

    # Importing OR-Tools is insufficient: this sentinel must solve an integer model.
    solver = create_solver(SolverBackend.ORTOOLS_GSCIP, "r12_integer_solver_sentinel")
    x = solver.add_var(vtype=SolverVarType.INTEGER, lb=0, ub=10, name="x")
    solver.add_constr(2 * x._raw >= 5, name="integer_lower_bound")
    solver.set_objective(x._raw, sense="minimize")
    solver.optimize()
    stats = asdict(solver.solve_stats())
    check(stats["status"] == "OPTIMAL" and abs(x.X - 3) < 1e-8, "GSCIP integer solve failed")
    result["solver_sentinel"] = {"value": x.X, "expected_value": 3, "solve": stats}

    hardware = source / "stream/inputs/examples/hardware/tpu_like_quad_core.yaml"
    workload = source / "stream/inputs/testing/workload/2conv_1_8_32_32_16_32_3.onnx"
    result["inputs"] = {
        "hardware": {"path": str(hardware), "sha256": sha256(hardware)},
        "workload": {"path": str(workload), "sha256": sha256(workload)},
    }
    result["configuration"] = {
        "backend": "ortools_gscip",
        "constraint_selection": {
            "memory_capacity": True,
            "object_fifo_depth": True,
            "buffer_descriptors": True,
            "dma_channels": True,
            "pipelining": "occupancy",
        },
        "mapping": "upstream auto-generated",
        "skip_if_exists": False,
    }
    # Upstream resolves referenced YAML paths from the checkout. It receives an
    # absolute output directory and reads the committed ONNX instead of generating it.
    os.chdir(source)
    stream_api.configure_logging()
    started = time.perf_counter()
    context = stream_api.optimize_allocation_co_generic(
        hardware=str(hardware),
        workload=str(workload),
        experiment_id="upstream-2conv",
        output_path=str(output / "pipeline"),
        backend="ortools_gscip",
        constraint_selection=ConstraintSelection(),
        skip_if_exists=False,
    )
    result["pipeline_wall_seconds"] = time.perf_counter() - started
    scheduler = context.get("scheduler")
    allocation = AllocationIR.from_internal(scheduler)
    allocation_path = output / "allocation_ir.json"
    allocation_path.write_text(allocation.model_dump_json(indent=2), encoding="utf-8")
    result["allocation_ir"] = str(allocation_path)
    result["solve"] = allocation.solve.model_dump(mode="json") if allocation.solve else None
    result["analytical_latency_cycles"] = context.get("total_latency")
    result["group_latencies"] = context.get("group_latencies")
    result["iterations"] = scheduler.iterations
    result["upstream_documented_reference_cycles"] = 14344
    result["matches_documented_reference"] = context.get("total_latency") == 14344
    result["cost_models"] = allocation.cost_models.model_dump(mode="json") if allocation.cost_models else None
    result["overlays"] = allocation.overlays
    check(allocation.backend == "ORTOOLS_GSCIP", "TETRA did not use GSCIP")
    check(allocation.solve is not None and allocation.solve.status == "OPTIMAL", "TETRA did not report OPTIMAL")
    check(context.get("total_latency") > 0, "Nonpositive upstream analytical latency")
    check(bool(allocation.mapping_nodes), "No node allocations returned")
    check(not allocation.overlays, "Unexpected out-of-tree overlay changed the baseline")
    if allocation.performance is not None:
        result["cost_degenerate"] = allocation.performance.aggregate.degenerate
        check(not allocation.performance.aggregate.degenerate, "Upstream cost model fell back to scalar estimation")

    # Inspect the actual solved transfer and path objects. This demonstrates the
    # available backend representation without inventing controller/NoC semantics.
    routes = []
    for transfer in scheduler.steady_state_workload.get_transfer_nodes():
        mapping = scheduler.mapping.get(transfer)
        # The solved TransferNode mapping stores a tuple of MulticastPathPlan
        # directly (SteadyStateScheduler.update_mapping_with_allocations).
        for path in mapping.resource_allocation:
            check(isinstance(path, MulticastPathPlan), "Unexpected solved transfer allocation type")
            routes.append(
                {
                    "transfer": transfer.name,
                    "tensor_bits": transfer.inputs[0].size_bits(),
                    "sources": [core.id for core in path.sources],
                    "targets": [core.id for core in path.targets],
                    "link_resources": [str(link) for link in path.links_used],
                    "upstream_single_firing_path_cycles": get_transfer_latency_for_path(transfer, path),
                }
            )
    result["chosen_transfer_paths"] = routes
    check(bool(routes), "TETRA produced no inspectable transfer paths")
    result["stream_status_after"] = git(source, "status", "--porcelain")
    check(result["stream_status_after"] == result["stream_status_before"], "Smoke modified the STREAM checkout")
    result["passed"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=R12 / "deps/stream")
    parser.add_argument("--output", type=Path, default=R12 / "results/baseline_smoke")
    args = parser.parse_args()
    source = args.stream.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "r12-baseline-smoke-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "upstream analytical fixture and actual solver execution",
        "wormhole_p0_qualified": False,
        "native_hardware_measurement": False,
        "source_visibility_semantics_tested": False,
        "controller_domain_semantics_tested": False,
        "passed": False,
    }
    try:
        run(source, output, result)
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finally:
        destination = output / "result.json"
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"passed": result["passed"], "result": str(destination)}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
