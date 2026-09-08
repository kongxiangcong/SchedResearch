"""Bounded R13 model integration qualification, not a performance comparison.

Seven declared two-chain micrographs, one maximum packet, and one rejected
oversized micrograph exercise representation and service boundaries. Only one
additional small graph receives the slower independent tick replay.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time

from event_machine import simulate as des
from independent_checker import audit_builder_rules, compare_core, simulate as tick_replay
from model_builder import Builder, HARDWARE, micro_graph, small_plan_space
from trace_audit import audit_trace

ROOT = Path(__file__).resolve().parent
SOURCES = ("test_model_integration.py", "model_builder.py", "event_machine.py", "independent_checker.py",
           "trace_audit.py", "hardware_model.json", "machine_contract.md")


def fingerprints():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def fingerprint_data(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compact_rules(rules):
    return {key: value for key, value in rules.items() if key != "expected_link_launches"}


def compact_trace(audit):
    keep = ("passed", "checked_output_blocks", "data_read_16B_blocks", "written_16B_blocks_including_controls",
            "observed_control_16B_blocks", "individual_memory_completion_events", "all_declared_operation_times_checked",
            "block_timeline_sha256", "failure_count", "failures")
    return {key: audit[key] for key in keep if key in audit}


def micro_cases():
    plans = small_plan_space()
    negative = next(plan for plan in plans if plan["nocs"] == [1, 1, 1]
                    and plan["placement"] == "same_group_other_channel"
                    and plan["chain1_offset_cycles"] == 0 and plan["source_wait"] == "source")
    return [
        {"name": "minimum_16B_payload", "payload": 16, "plan": plans[0]},
        {"name": "32B_negative_direction_wraps", "payload": 32, "plan": negative},
        {"name": "48B_partial_last_flit_zero_niu_extra", "payload": 48, "plan": negative,
         "params": {"niu_processing_cycles": 0}},
        {"name": "1024B_single_niu_flit_capacity", "payload": 1024, "plan": plans[0],
         "params": {"niu_buffer_flits": 1}},
        {"name": "32B_long_credit_return", "payload": 32, "plan": plans[-1],
         "params": {"credit_cycles": 36}},
        {"name": "48B_serial_bank_completions", "payload": 48, "plan": negative, "bank_layout": "mono"},
        {"name": "16B_descending_long_path_tick_check", "payload": 16, "plan": plans[-1],
         "tie_break": "descending", "tick_check": True},
    ]


def standalone_packet():
    """8KiB data-copy only: no compute scratch or multi-epoch alias assumption."""
    builder = Builder()
    source = builder.span((9, 11), 0x10000, 8192)
    target = builder.span((1, 1), 0x20000, 8192)
    builder.packet("max_packet", (9, 11), (1, 1), 0, payload_src=source, payload_dst=target)
    builder.spec["metadata"] = {"params": builder.params, "bank_layout": builder.bank_layout,
                                "tags": builder.tags, "packets": builder.packets,
                                "plan": {"chain1_offset_cycles": 0}}
    return builder.spec, source, target


def packet_copy_audit(spec, execution, source, target):
    """Independent one-packet 16B provenance audit, explicitly not audit_trace."""
    faults = []
    memory = {block: (index * 7919 + 17, index) for index, block in enumerate(source)}
    expected = {block: (index * 7919 + 17, index) for index, block in enumerate(target)}
    captured = defaultdict(dict)
    by_id = {operation["id"]: operation for operation in execution["operations"]}
    declared = {f"{job['id']}:{i}" for job in spec["jobs"] for i in range(len(job["ops"]))}
    if set(by_id) != declared or len(by_id) != len(execution["operations"]):
        faults.append("operation coverage or duplicate")
    events = []
    for operation_id, tag in spec["metadata"]["tags"].items():
        for i, offset in enumerate(tag.get("block_completion_ticks", [])):
            if operation_id not in by_id:
                faults.append(f"missing operation {operation_id}")
                continue
            events.append((by_id[operation_id]["start"] + offset, operation_id, i, tag))
    read_count = write_count = 0
    for _, _, index, tag in sorted(events, key=lambda row: row[:3]):
        block = tag["blocks"][index]
        if tag["kind"] == "read":
            captured[tag["value_key"]][index] = memory.get(block)
            read_count += 1
        elif tag["kind"] == "write":
            memory[block] = captured[tag["value_key"]].get(index)
            write_count += 1
    if any(memory.get(block) != value for block, value in expected.items()):
        faults.append("target content or 16B provenance mismatch")
    if read_count != 512 or write_count != 512:
        faults.append("8KiB block read/write count mismatch")
    return {"passed": execution["status"] == "ok" and not faults, "read_blocks": read_count,
            "written_blocks": write_count, "failures": faults,
            "scope": "single packet with512 distinct16B blocks; no compute, ACK, epoch, or DFG lifetime claim"}


def rejected_oversized_micrograph():
    payload = 8192
    rf_budget = HARDWARE["model_choices"]["rf_scratch_bytes_per_tile"]
    # The complete micrograph holds captured input and compute output. Its
    # registered per-tile scratch budget cannot cover this oversized payload.
    reasons = []
    if 2 * payload > rf_budget:
        reasons.append({"code": "compute_scratch_exceeds_registered_budget", "required_bytes": 2 * payload,
                        "budget_bytes": rf_budget})
    if payload > 0x1000:
        reasons.append({"code": "fixed_epoch_dram_stride_would_alias", "payload_bytes": payload,
                        "registered_builder_stride_bytes": 0x1000})
    return {"name": "8192B_complete_micrograph_preflight_rejected", "expected": "reject",
            "passed": len(reasons) == 2, "rejected": bool(reasons), "reasons": reasons,
            "execution": "not executed because the declared complete micrograph would violate capacity and ownership",
            "scope": "independent preflight only; this result does not assert that model_builder itself rejects this input"}


def run():
    hashes_before = fingerprints()
    start = time.perf_counter()
    rows = []
    tick_row = None
    for case in micro_cases():
        spec = micro_graph(case["plan"], case.get("params"), payload_bytes=case["payload"],
                           bank_layout=case.get("bank_layout", "interleaved"),
                           tie_break=case.get("tie_break", "ascending"))
        rules = audit_builder_rules(spec, HARDWARE)
        execution = des(spec)
        values = audit_trace(spec, execution)
        row = {"name": case["name"], "expected": "complete", "payload_bytes": case["payload"],
               "plan_id": case["plan"]["id"], "params": spec["metadata"]["params"],
               "bank_layout": spec["metadata"]["bank_layout"], "tie_break": spec["tie_break"],
               "spec_sha256": fingerprint_data(spec), "execution_sha256": fingerprint_data(execution),
               "status": execution["status"], "quiescent_ticks": execution["quiescent"],
               "operations": len(execution["operations"]), "builder_rules": compact_rules(rules),
               "trace_audit": compact_trace(values),
               "passed": rules["passed"] and values["passed"] and execution["status"] == "ok"}
        if case.get("tick_check"):
            before_tick = time.perf_counter()
            independent = tick_replay(spec, max_ticks=2_000_000)
            differences = compare_core(independent, execution)
            tick_row = {"name": case["name"], "passed": not differences,
                        "tick_wall_seconds": time.perf_counter() - before_tick,
                        "quiescent_ticks": independent["quiescent"], "mismatches": differences,
                        "scope": "all operation start/end/resources/locks, job ends, credit quiescence and buffer peaks"}
            row["passed"] = row["passed"] and tick_row["passed"]
        rows.append(row)
        print(json.dumps({"name": row["name"], "passed": row["passed"], "status": row["status"]}), flush=True)

    spec, source, target = standalone_packet()
    rules = audit_builder_rules(spec, HARDWARE)
    execution = des(spec)
    copy = packet_copy_audit(spec, execution, source, target)
    rows.append({"name": "8192B_maximum_packet_both_dimensions_wrap", "expected": "complete",
                 "spec_sha256": fingerprint_data(spec), "execution_sha256": fingerprint_data(execution),
                 "payload_bytes": 8192, "status": execution["status"], "quiescent_ticks": execution["quiescent"],
                 "builder_rules": compact_rules(rules), "packet_copy_audit": copy,
                 "trace_audit": {"not_applicable": "audit_trace is a named two-chain DFG auditor; this fixture is a single packet"},
                 "passed": rules["passed"] and copy["passed"] and execution["status"] == "ok"})
    rows.append(rejected_oversized_micrograph())
    hashes_after = fingerprints()
    npe_receipt = json.loads((ROOT / "artifacts/npe_projection.json").read_text(encoding="utf-8"))
    report = {"schema": "r13.model-integration.v1",
              "command": "research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/test_model_integration.py",
              "registered_case_count": 9, "source_hashes": hashes_before,
              "source_unchanged_during_run": hashes_before == hashes_after,
              "passed": hashes_before == hashes_after and all(row["passed"] for row in rows),
              "cases": rows, "additional_independent_tick": tick_row,
              "wall_seconds_not_model_time": time.perf_counter() - start,
              "cross_tool_status": npe_receipt["cross_tool_status"],
              "M0_statement": "These integration checks can pass while the requested NPE cross-tool step remains not executed. Do not report the entire cross-tool validation chain as passed.",
              "scope": "bounded representation/service/lifecycle boundaries, not exhaustive plans, performance sensitivity, compiler gain, or full MLP"}
    destination = ROOT / "artifacts/integration_qualification.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "cases": len(rows), "source_unchanged": hashes_before == hashes_after,
                      "NPE_cross_tool_status": report["cross_tool_status"], "output": str(destination)}))
    return report


if __name__ == "__main__":
    raise SystemExit(0 if run()["passed"] else 1)
