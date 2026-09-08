"""Apply the registered narrow cost overlay in one process, then really solve TETRA."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
from math import ceil
from pathlib import Path
import traceback

import baseline_smoke


R12 = Path(__file__).resolve().parent
SOURCE = R12 / "deps/stream"
CONTRACT = R12 / "shared_resource_counterfactual_contract.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def run(output: Path, result: dict) -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    result["contract_sha256"] = sha(CONTRACT)
    result["runner_sha256"] = sha(Path(__file__))
    for role in ("hardware", "workload"):
        check(sha(SOURCE / contract["inputs"][role]) == contract["inputs"][role + "_sha256"], "Input changed")
    original_files = [R12 / "results/baseline_smoke" / name for name in ("result.json", "allocation_ir.json")]
    originals_before = {str(p.relative_to(R12)): sha(p) for p in original_files}
    original = json.loads(original_files[0].read_text(encoding="utf-8"))
    check(original["analytical_latency_cycles"] == 12808, "Original fixture changed")

    from stream.opt.allocation.constraint_optimization import utils
    from stream.opt.allocation.constraint_optimization import transfer_and_tensor_allocation as allocator
    from stream.workload.node import TransferType

    original_helper = utils.get_transfer_latency_for_path
    original_allocator_binding = allocator.get_transfer_latency_for_path
    check(original_helper is original_allocator_binding, "Unexpected upstream helper bindings")
    check(Path(utils.__file__).resolve().is_relative_to(SOURCE), "Wrong source import")
    calls = {"all": 0, "changed": []}

    def overlay(transfer, path):
        old = original_helper(transfer, path)
        calls["all"] += 1
        eligible = (
            transfer.name == "Transfer(conv1_out)"
            and transfer.transfer_type == TransferType.COMPUTE_TO_COMPUTE
            and len(transfer.inputs) == 1
            and transfer.inputs[0].shape == (1, 16, 32, 32)
            and transfer.inputs[0].size_bits() == 262144
            and path is not None
            and [c.id for c in path.sources] == [0, 1, 2, 3]
            and [c.id for c in path.targets] == [0, 1, 2, 3]
            and len(path.links_used) == 1
        )
        if eligible:
            link = path.links_used[0]
            eligible = link.sender == "Any" and link.receiver == "Any" and link.bidirectional and link.bandwidth == 128
        if not eligible:
            return old
        new = ceil(transfer.inputs[0].size_bits() / path.links_used[0].bandwidth)
        check(old == 512 and new == 2048, "Eligible cost differs from registered intervention")
        caller = inspect.currentframe().f_back
        calls["changed"].append({
            "transfer": transfer.name, "tensor_bits": transfer.inputs[0].size_bits(),
            "old_cycles": old, "overlay_cycles": new,
            "caller_module": caller.f_globals.get("__name__"), "caller_function": caller.f_code.co_name,
        })
        return new

    # Both documented references are patched. The trace helper resolves the
    # patched utils global at call time, so it receives the same cost too.
    utils.get_transfer_latency_for_path = overlay
    allocator.get_transfer_latency_for_path = overlay
    result["process_overlay"]["bindings_verified"] = (
        utils.get_transfer_latency_for_path is overlay and allocator.get_transfer_latency_for_path is overlay
    )
    try:
        baseline_smoke.run(SOURCE, output, result)
    finally:
        utils.get_transfer_latency_for_path = original_helper
        allocator.get_transfer_latency_for_path = original_allocator_binding
        result["process_overlay"]["helper_calls"] = calls["all"]
        result["process_overlay"]["changed_calls"] = calls["changed"]
        result["process_overlay"]["changed_call_count"] = len(calls["changed"])

    check(bool(calls["changed"]), "Overlay never triggered")
    check(any(c["caller_module"] == allocator.__name__ for c in calls["changed"]), "Overlay did not enter allocator")
    selected = [p for p in result["chosen_transfer_paths"] if p["transfer"] == "Transfer(conv1_out)"]
    check(len(selected) == 1, "Missing chosen transfer")
    result["selected_conv1_transfer"] = selected[0]
    new_ir = json.loads((output / "allocation_ir.json").read_text(encoding="utf-8"))
    old_ir = json.loads(original_files[1].read_text(encoding="utf-8"))
    result["mapping_nodes_identical_to_original"] = new_ir["mapping_nodes"] == old_ir["mapping_nodes"]
    result["fusion_splits_identical_to_original"] = new_ir["fusion_splits"] == old_ir["fusion_splits"]
    result["original_artifact_sha256_before"] = originals_before
    result["original_artifact_sha256_after"] = {str(p.relative_to(R12)): sha(p) for p in original_files}
    check(result["original_artifact_sha256_before"] == result["original_artifact_sha256_after"], "Original smoke changed")
    result["fixed_plan_arithmetic_prediction"] = 14344
    result["reoptimized_analytical_cycles"] = result["analytical_latency_cycles"]
    result["passed"] = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=R12 / "results/shared_resource_counterfactual")
    args = parser.parse_args()
    output = args.output.resolve()
    check(output.is_relative_to(R12 / "results"), "Output must be a new R12 results directory")
    check(not output.exists(), "Output already exists; use a new directory")
    output.mkdir(parents=True)
    result = {
        "schema": "r12.shared-resource-counterfactual.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "uncalibrated analytical fixture reoptimized with explicit process-local cost overlay",
        "process_overlay": {"id": "registered-single-shared-bus-conservation", "source_files_edited": False},
        "note_on_allocation_overlays": "AllocationIR overlays lists only installed upstream overlays; the explicit process_overlay field above is authoritative for this intervention",
        "wormhole_p0_qualified": False, "native_hardware_measurement": False,
        "source_visibility_semantics_tested": False, "controller_domain_semantics_tested": False,
        "H1_performance_result": False, "P1_algorithm": False, "passed": False,
    }
    try:
        run(output, result)
    except Exception as error:
        result["passed"] = False
        result["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    finally:
        destination = output / "result.json"
        destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"passed": result["passed"], "overlay_changed_calls": result["process_overlay"].get("changed_call_count"),
                          "analytical_cycles": result.get("analytical_latency_cycles"), "result": str(destination)}))
    raise SystemExit(0 if result["passed"] else 1)
