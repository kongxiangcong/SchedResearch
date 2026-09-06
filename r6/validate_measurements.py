"""R6 measurement-record checks. No simulator, effect estimator, or acceptance claim.

Unknown observations use {"value": null, "unknown_reason": "..."}.
Exit 0: structurally valid; 1: invalid record; 2: --require-mechanism not eligible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from datetime import datetime

SCHEMA = "r6.measurement.v1"
SPLITS = ("pilot", "train", "validation", "test")
KINDS = ("fixed_binary_interference", "compiler_variant", "dynamic_recovery")
METRICS = ("elapsed_device_ns", "elapsed_host_ns", "traffic", "compute_active", "request_observation")
CONTRACT_FIELDS = ("semantic_workload_sha256", "binary_sha256", "layout_sha256", "input_sha256",
                   "initial_state_sha256", "software_sha256", "frequency", "implementation", "memory")
STATIC_DIMENSIONS = ("fusion_residency", "tiling", "reuse", "buffering", "capacity", "bank_layout",
                     "prefetch", "resource_order", "outstanding")


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(record, base_dir):
    errors, blockers = [], []
    result = {"record_valid": False, "device_screening_eligible": False,
              "mechanism_gate_eligible": False, "performance_gate_evaluated": False,
              "errors": errors, "blockers": blockers,
              "warning": "Documentary checks only; raw provenance, numerical validity and causal claims require independent audit."}

    def error(message):
        if message not in errors:
            errors.append(message)

    def block(message):
        if message not in blockers:
            blockers.append(message)

    def need(condition, message):
        if not condition:
            block(message)

    def observe(obs, label, instrument_ids, required=True):
        if not isinstance(obs, dict) or "value" not in obs:
            error(label + ": expected observation object with value")
            return None
        value = obs["value"]
        if value is None:
            if not nonempty(obs.get("unknown_reason")):
                error(label + ": null requires unknown_reason")
            if required:
                block(label + ": unavailable")
        else:
            if obs.get("unknown_reason") is not None:
                error(label + ": known value cannot have unknown_reason")
            if obs.get("instrument_id") not in instrument_ids:
                error(label + ": unknown instrument_id")
        return value

    if not isinstance(record, dict):
        error("top level must be an object")
        return result
    if record.get("schema_version") != SCHEMA:
        error("unsupported schema_version")
    if record.get("purpose") not in ("screening", "mechanism_gate"):
        error("purpose must be screening or mechanism_gate")
    evidence = record.get("evidence", {})
    if not isinstance(evidence, dict):
        error("evidence must be an object")
        return result
    if evidence.get("level") not in ("unavailable", "device", "rtl_config", "cpu", "functional_sdk"):
        error("unknown evidence level")
    need(evidence.get("level") == "device", "physical target device evidence required")
    need(evidence.get("physical_npu_confirmed") is True, "physical NPU execution unconfirmed")
    need(evidence.get("execution_confirmed") is True, "execution unconfirmed")
    need(nonempty(evidence.get("target")), "target identity missing")
    need(record.get("fixture") is False, "fixture or unclassified provenance cannot qualify")

    artifacts = {}
    for item in record.get("artifacts", []):
        identity = item.get("id")
        if not nonempty(identity) or identity in artifacts:
            error("artifact IDs must be unique nonempty strings")
        artifacts[identity] = item
        if not sha(item.get("sha256")) or not nonempty(item.get("path")):
            error(f"artifact {identity}: path and SHA256 required")
            continue
        path = Path(item["path"])
        path = path if path.is_absolute() else Path(base_dir) / path
        if not path.is_file():
            error(f"artifact {identity}: missing file")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            error(f"artifact {identity}: SHA256 mismatch")

    def artifact_ref(identity, label):
        need(identity in artifacts, label + ": verified artifact reference missing")

    instruments = {}
    for inst in record.get("instrumentation", []):
        identity = inst.get("id")
        if not nonempty(identity) or identity in instruments:
            error("instrument IDs must be unique nonempty strings")
        instruments[identity] = inst
        for key in ("definition", "unit", "clock_domain", "sampling_boundary", "wrap_handling",
                    "multiplex_handling", "reset_rule"):
            need(nonempty(inst.get(key)), f"instrument {identity}: {key} undefined")
        need(isinstance(inst.get("bit_width"), int) and inst["bit_width"] > 0,
             f"instrument {identity}: bit_width undefined")
        sync = inst.get("clock_sync", {})
        need(nonempty(sync.get("method")) and number(sync.get("max_error_ns")),
             f"instrument {identity}: clock synchronization/uncertainty undefined")

    contracts = {}
    for contract in record.get("contracts", []):
        identity, data = contract.get("id"), contract.get("data", {})
        if not nonempty(identity) or identity in contracts:
            error("contract IDs must be unique nonempty strings")
        contracts[identity] = data
        if contract.get("sha256") != canonical_hash(data):
            error(f"contract {identity}: canonical SHA256 mismatch")
        for key in CONTRACT_FIELDS:
            item = data.get(key)
            need(item is not None and (not key.endswith("_sha256") or sha(item)),
                 f"contract {identity}: {key} not frozen")
        for key in ("binary", "layout", "input", "semantic_workload", "software", "initial_state"):
            ref = data.get(key + "_artifact_id")
            artifact_ref(ref, f"contract {identity} {key}")
            if ref in artifacts and data.get(key + "_sha256") != artifacts[ref].get("sha256"):
                error(f"contract {identity}: {key} artifact digest disagreement")
        impl = data.get("implementation") or {}
        for key in ("dtype", "kernels", "shapes", "compiler_options", "ops", "output_acceptance"):
            need(impl.get(key) is not None, f"contract {identity}: implementation.{key} missing")
        freq = data.get("frequency") or {}
        need(isinstance(freq.get("configured_hz"), dict) and bool(freq["configured_hz"]),
             f"contract {identity}: frequency configuration missing")
        need(number(freq.get("actual_tolerance_pct")), f"contract {identity}: frequency tolerance missing")
        memory = data.get("memory") or {}
        for key in ("capacity_bytes", "address_mapping", "residency_scope", "alias_last_reader", "warm_cold_rule"):
            need(memory.get(key) is not None, f"contract {identity}: memory.{key} missing")

    pre = record.get("preregistration", {})
    plan = pre.get("data", {})
    if pre.get("sha256") != canonical_hash(plan):
        error("preregistration canonical SHA256 mismatch")
    need(plan.get("net_improvement_threshold_pct") == 5.0, "preregistered net improvement threshold must be 5%")
    need(plan.get("paired_ci_lower_bound_required_gt") == 0, "preregistered paired CI lower bound must exceed zero")
    need(plan.get("min_test_pairs_per_condition_per_session", 0) >= 30, "at least 30 test paired blocks per condition/session required")
    need(plan.get("min_test_sessions", 0) >= 2, "at least two test sessions required")
    need(plan.get("min_non_extreme_interference_conditions", 0) >= 2, "at least two non-extreme interference conditions required")
    need(number(plan.get("isolated_max_regression_pct")), "isolated regression tolerance must be preregistered")
    need(nonempty(plan.get("ci_method")), "paired/session-aware CI method must be preregistered")
    try:
        frozen = datetime.fromisoformat(plan["frozen_at"])
        need(frozen.tzinfo is not None, "preregistration timestamp must include timezone")
    except (KeyError, ValueError, TypeError):
        frozen = None
        block("preregistration timestamp missing or invalid")
    schedules, seen_seeds = {}, {}
    for split in SPLITS:
        seeds = plan.get("seeds", {}).get(split, [])
        if not isinstance(seeds, list) or any(not isinstance(s, int) or isinstance(s, bool) for s in seeds):
            error(f"{split}: seeds must be integer list")
            seeds = []
        if len(seeds) != len(set(seeds)):
            error(f"{split}: duplicate registered seed")
        schedules[split] = set(seeds)
        for seed in seeds:
            if seed in seen_seeds:
                error(f"split overlap: seed {seed} in {seen_seeds[seed]} and {split}")
            seen_seeds[seed] = split
    for split in ("train", "validation", "test"):
        need(bool(schedules[split]), f"independent {split} seed schedule missing")

    conditions = {}
    for condition in record.get("conditions", []):
        identity = condition.get("id")
        if not nonempty(identity) or identity in conditions:
            error("condition IDs must be unique nonempty strings")
        conditions[identity] = condition
        if not isinstance(condition.get("isolation"), bool) or not isinstance(condition.get("extreme"), bool):
            error(f"condition {identity}: isolation/extreme flags required")
        if not condition.get("isolation"):
            for key in ("master_id", "program_sha256", "input_sha256", "read_write_ratio", "address_range",
                        "working_set_bytes", "offered_bytes", "phase_rule"):
                need(condition.get(key) is not None, f"condition {identity}: background {key} missing")
    need(any(c.get("isolation") for c in conditions.values()), "isolation condition missing")

    comparisons = {}
    for comparison in record.get("comparisons", []):
        identity, kind = comparison.get("id"), comparison.get("kind")
        if not nonempty(identity) or identity in comparisons:
            error("comparison IDs must be unique nonempty strings")
        comparisons[identity] = comparison
        if kind not in KINDS:
            error(f"comparison {identity}: unknown kind")
        b = contracts.get(comparison.get("baseline_contract_id"))
        c = contracts.get(comparison.get("candidate_contract_id"))
        if b is None or c is None:
            error(f"comparison {identity}: unknown contract")
            continue
        if kind in ("fixed_binary_interference", "dynamic_recovery") and b != c:
            error(f"comparison {identity}: {kind} requires identical full contract")
        if kind == "compiler_variant":
            for key in ("semantic_workload_sha256", "input_sha256", "initial_state_sha256", "software_sha256", "frequency"):
                if b.get(key) != c.get(key):
                    error(f"comparison {identity}: compiler comparison changed fixed {key}")
        if kind == "dynamic_recovery":
            intervention = comparison.get("intervention", {})
            artifact_ref(intervention.get("policy_artifact_id"), f"comparison {identity} causal policy")
            obs_ids = intervention.get("causal_instrument_ids", [])
            need(bool(obs_ids) and all(i in instruments for i in obs_ids), f"comparison {identity}: causal observability missing")
            need(number(intervention.get("finite_state_bytes")), f"comparison {identity}: finite state budget missing")
            for key in ("control_latency_charged", "extra_traffic_charged", "frequency_effect_charged"):
                need(intervention.get(key) is True, f"comparison {identity}: {key} unverified")

    runs, pairs, test_seed_sessions = {}, {}, {}
    usable_elapsed = False
    for run in record.get("runs", []):
        rid = run.get("id")
        if not nonempty(rid) or rid in runs:
            error("run IDs must be unique nonempty strings")
        runs[rid] = run
        split, seed, session = run.get("split"), run.get("phase_seed"), run.get("session_id")
        if split not in SPLITS or seed not in schedules.get(split, set()):
            error(f"run {rid}: split/phase seed not in frozen schedule")
        if not nonempty(session):
            error(f"run {rid}: session_id missing")
        if run.get("status") not in ("completed", "failed", "timeout"):
            error(f"run {rid}: invalid status")
        need(run.get("status") == "completed", f"run {rid}: failed/timeout must be retained and resolved")
        need(run.get("numerical_pass") is True, f"run {rid}: numerical acceptance unverified")
        artifact_ref(run.get("raw_artifact_id"), f"run {rid} raw observations")
        contract = contracts.get(run.get("contract_id"))
        if contract is None:
            error(f"run {rid}: unknown contract")
            contract = {}
        condition = conditions.get(run.get("condition_id"))
        if condition is None:
            error(f"run {rid}: unknown condition")
        metrics = run.get("metrics", {})
        values = {key: observe(metrics.get(key), f"run {rid} {key}", instruments,
                                required=key != "elapsed_host_ns") for key in METRICS}
        for key in ("elapsed_device_ns", "elapsed_host_ns"):
            value = values[key]
            if value is not None and (not number(value) or value <= 0):
                error(f"run {rid}: {key} must be positive finite")
            usable_elapsed |= (number(value) and value > 0 and run.get("status") == "completed"
                               and run.get("numerical_pass") is True and run.get("raw_artifact_id") in artifacts)
        traffic = values["traffic"]
        if traffic is not None:
            ports = traffic.get("ports", []) if isinstance(traffic, dict) else []
            if not ports:
                error(f"run {rid}: traffic requires per-port actual byte counters")
            for port in ports:
                if not nonempty(port.get("id")):
                    error(f"run {rid}: traffic port ID missing")
                for direction in ("read", "write"):
                    counts = [port.get(direction + "_" + stage + "_bytes") for stage in ("requested", "accepted", "completed")]
                    if not all(number(v) for v in counts):
                        error(f"run {rid}: actual {direction} traffic counts missing/invalid")
                    elif not counts[0] >= counts[1] >= counts[2]:
                        error(f"run {rid}: {direction} traffic conservation violated")
        active = values["compute_active"]
        if active is not None:
            engines = active.get("engines", []) if isinstance(active, dict) else []
            if not engines:
                error(f"run {rid}: compute-active requires per-engine actual counts")
            for engine in engines:
                if not number(engine.get("active_cycles")) or not number(engine.get("elapsed_cycles")):
                    error(f"run {rid}: invalid compute-active counts")
                elif engine["active_cycles"] > engine["elapsed_cycles"]:
                    error(f"run {rid}: engine active exceeds engine elapsed")
        request = values["request_observation"]
        if request is not None:
            if not isinstance(request, dict) or request.get("kind") not in ("request_trace", "limit", "latency_buckets"):
                error(f"run {rid}: request observation kind undefined")
            elif not nonempty(request.get("boundary_definition")) or not request.get("counters"):
                error(f"run {rid}: request boundaries/counters missing")
            elif not all(number(v) for v in request["counters"].values()):
                error(f"run {rid}: request counts must be finite nonnegative")
            elif request["kind"] == "limit":
                counters = request["counters"]
                required = ("configured_limit", "observed_peak", "at_limit_cycles")
                if not all(number(counters.get(key)) for key in required):
                    error(f"run {rid}: limit needs configured_limit, observed_peak and at_limit_cycles")
                elif counters["configured_limit"] <= 0 or counters["observed_peak"] > counters["configured_limit"]:
                    error(f"run {rid}: limit/peak inconsistency")
            elif request["kind"] == "latency_buckets":
                bounds = request.get("bucket_upper_bounds_ns", [])
                counts_value = request.get("bucket_counts", [])
                if (not bounds or not all(number(v) for v in bounds) or bounds != sorted(set(bounds)) or
                        len(counts_value) != len(bounds) + 1 or not all(number(v) for v in counts_value)):
                    error(f"run {rid}: latency histogram needs ordered bounds and counts including final overflow-range bucket")
                elif request["counters"].get("observed_requests") != sum(counts_value):
                    error(f"run {rid}: latency histogram count conservation violated")
            if isinstance(request, dict) and request.get("kind") == "request_trace":
                artifact_ref(request.get("trace_artifact_id"), f"run {rid} request trace")
        quality = run.get("capture_quality", {})
        for key in ("dropped_records", "overflow_count", "unhandled_wraps"):
            val = quality.get(key)
            need(val == 0 and isinstance(val, int) and not isinstance(val, bool), f"run {rid}: {key} nonzero or unknown; recapture required")
        actual = observe(run.get("actual_frequency_hz"), f"run {rid} actual_frequency_hz", instruments)
        freq = contract.get("frequency") or {}
        if actual is not None:
            configured = freq.get("configured_hz", {})
            if not isinstance(actual, dict) or not actual:
                error(f"run {rid}: actual frequencies must identify clock domains")
            else:
                for domain, configured_hz in configured.items():
                    measured = actual.get(domain)
                    need(number(measured) and number(configured_hz) and configured_hz > 0 and
                         number(freq.get("actual_tolerance_pct")) and
                         abs(measured - configured_hz) / configured_hz * 100 <= freq["actual_tolerance_pct"],
                         f"run {rid}: frequency outside frozen tolerance or unavailable ({domain})")
        background = observe(run.get("background_actual_bytes"), f"run {rid} background_actual_bytes", instruments)
        if background is not None and not number(background):
            error(f"run {rid}: background actual bytes invalid")
        if condition and condition.get("isolation") and background not in (None, 0):
            error(f"run {rid}: isolation background traffic is nonzero")
        if split == "test":
            try:
                capture_time = datetime.fromisoformat(run["captured_at"])
                need(frozen is not None and frozen.tzinfo is not None and capture_time.tzinfo is not None and capture_time >= frozen,
                     f"run {rid}: test predates preregistration or timestamp lacks timezone")
            except (KeyError, ValueError, TypeError):
                block(f"run {rid}: valid capture timestamp missing")
            old = test_seed_sessions.setdefault(seed, session)
            need(old == session, f"test seed {seed} reused across sessions; independent new phases required")
        comparison_id = run.get("comparison_id")
        if comparison_id is not None:
            if comparison_id not in comparisons:
                error(f"run {rid}: unknown comparison")
            if run.get("arm") not in ("baseline", "candidate") or run.get("pair_order") not in (0, 1):
                error(f"run {rid}: paired arm/order invalid")
            if not nonempty(run.get("pair_id")):
                error(f"run {rid}: pair_id missing")
            key = (comparison_id, session, split, run.get("pair_id"))
            pairs.setdefault(key, []).append(run)
        else:
            block(f"run {rid}: unpaired screening record")

    counts, orders, condition_ids, counted_seeds = {}, {}, set(), {}
    for (cid, session, split, pid), members in pairs.items():
        if len(members) != 2 or {r.get("arm") for r in members} != {"baseline", "candidate"}:
            error(f"pair {pid}: exactly one baseline and one candidate required")
            continue
        b, c = sorted(members, key=lambda r: r["arm"])
        comparison = comparisons.get(cid, {})
        if {b.get("pair_order"), c.get("pair_order")} != {0, 1}:
            error(f"pair {pid}: execution order must be 0/1")
        if b.get("phase_seed") != c.get("phase_seed"):
            error(f"pair {pid}: phase seed mismatch")
        for arm, run in (("baseline", b), ("candidate", c)):
            if run.get("contract_id") != comparison.get(arm + "_contract_id"):
                error(f"pair {pid}: arm contract mismatch")
        cond_id = c.get("condition_id")
        if comparison.get("kind") == "fixed_binary_interference":
            if not conditions.get(b.get("condition_id"), {}).get("isolation") or conditions.get(cond_id, {}).get("isolation"):
                error(f"pair {pid}: fixed interference requires isolated baseline and interfering candidate")
        elif b.get("condition_id") != cond_id:
            error(f"pair {pid}: compiler/dynamic pair must use same condition")
        if comparison.get("kind") in ("fixed_binary_interference", "dynamic_recovery"):
            def completed(run):
                value = run.get("metrics", {}).get("traffic", {}).get("value")
                if not isinstance(value, dict):
                    return None
                return sorted((p.get("id"), p.get("read_completed_bytes"), p.get("write_completed_bytes")) for p in value.get("ports", []))
            if completed(b) != completed(c):
                error(f"pair {pid}: fixed-contract completed payload bytes differ")
        if split == "test":
            key = (cid, cond_id, session)
            seeds = counted_seeds.setdefault(key, set())
            if b.get("phase_seed") in seeds:
                error(f"pair {pid}: duplicate independent phase seed within condition/session")
            seeds.add(b.get("phase_seed"))
            counts[key] = counts.get(key, 0) + 1
            orders.setdefault(key, set()).add(b.get("pair_order"))
            condition_ids.add((cid, cond_id))

    need(bool(comparisons), "no comparison matrix")
    for cid, comparison in comparisons.items():
        tested = [cond for comp, cond in condition_ids if comp == cid]
        non_extreme = [cond for cond in tested if not conditions.get(cond, {}).get("isolation") and not conditions.get(cond, {}).get("extreme")]
        need(len(non_extreme) >= plan.get("min_non_extreme_interference_conditions", 2), f"comparison {cid}: fewer than two non-extreme test interference conditions")
        if comparison.get("kind") == "dynamic_recovery":
            need(any(conditions.get(cond, {}).get("isolation") for cond in tested), f"comparison {cid}: isolated regression control missing")
        for cond in tested:
            sessions = [session for comp, condition, session in counts if comp == cid and condition == cond]
            need(len(sessions) >= plan.get("min_test_sessions", 2), f"comparison {cid}/{cond}: fewer than two test sessions")
            for session in sessions:
                key = (cid, cond, session)
                need(counts[key] >= plan.get("min_test_pairs_per_condition_per_session", 30), f"comparison {cid}/{cond}/{session}: fewer than 30 paired blocks")
                need(orders[key] == {0, 1}, f"comparison {cid}/{cond}/{session}: pair execution order not varied")

    strong = record.get("strong_static", {})
    need(strong.get("selected_contract_id") in contracts, "strong-static selected contract missing")
    selected_id = strong.get("selected_contract_id")
    for cid, comparison in comparisons.items():
        if comparison.get("kind") == "dynamic_recovery":
            need(comparison.get("baseline_contract_id") == selected_id and comparison.get("candidate_contract_id") == selected_id,
                 f"comparison {cid}: dynamic contract is not the selected strong-static contract")
            residual_controls = [item for item in comparisons.values() if item.get("kind") == "fixed_binary_interference"
                                 and item.get("baseline_contract_id") == selected_id and item.get("candidate_contract_id") == selected_id]
            need(bool(residual_controls), f"comparison {cid}: selected strong-static same-binary residual control missing")
            residual_ids = {item["id"] for item in residual_controls}
            residual_conditions = {condition for comp, condition in condition_ids if comp in residual_ids}
            for comp, condition in condition_ids:
                if comp == cid and not conditions.get(condition, {}).get("isolation"):
                    need(condition in residual_conditions,
                         f"comparison {cid}/{condition}: matching selected-static residual test condition missing")
    need(strong.get("selected_on") == "validation" and strong.get("test_used_for_selection") is False,
         "strong-static requires training search, validation-only selection, untouched test")
    artifact_ref(strong.get("selection_artifact_id"), "strong-static selection")
    need(strong.get("search_budget") is not None, "strong-static search budget missing")
    for dimension in STATIC_DIMENSIONS:
        entry = strong.get("dimensions", {}).get(dimension, {})
        need(entry.get("status") in ("evaluated", "unsupported") and nonempty(entry.get("reason")),
             f"strong-static {dimension}: evaluated/unsupported evidence missing")
        artifact_ref(entry.get("artifact_id"), f"strong-static {dimension}")
    for name in ("empty_run", "known_bytes_copy", "single_compute", "instrumentation_overhead"):
        calibration = record.get("calibration", {}).get(name, {})
        need(calibration.get("verified") is True, f"calibration {name}: unverified")
        artifact_ref(calibration.get("artifact_id"), f"calibration {name}")
    need(record.get("calibration", {}).get("overhead_charged") is True, "instrumentation overhead not charged")
    kinds = {c.get("kind") for c in comparisons.values()}
    need("fixed_binary_interference" in kinds, "same-binary interference loss control missing")
    need("dynamic_recovery" in kinds, "no dynamic recovery comparison; screening/static work only")
    need(bool(runs), "no runs recorded")
    result["record_valid"] = not errors
    result["device_screening_eligible"] = (not errors and record.get("fixture") is False and evidence.get("level") == "device"
                                           and evidence.get("physical_npu_confirmed") is True
                                           and evidence.get("execution_confirmed") is True and usable_elapsed)
    result["mechanism_gate_eligible"] = not errors and not blockers
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--base-dir", type=Path)
    parser.add_argument("--require-mechanism", action="store_true")
    args = parser.parse_args()
    try:
        record = json.loads(args.record.read_text(encoding="utf-8-sig"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON " + x)))
        result = validate(record, args.base_dir or args.record.parent)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        result = {"record_valid": False, "device_screening_eligible": False,
                  "mechanism_gate_eligible": False, "performance_gate_evaluated": False,
                  "errors": ["Malformed record: " + str(exc)], "blockers": []}
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 1 if not result["record_valid"] else 2 if args.require_mechanism and not result["mechanism_gate_eligible"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
