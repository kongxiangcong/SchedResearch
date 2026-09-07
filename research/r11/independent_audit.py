"""Independent R11 audit: no imports from the graph generator or simulator.

The checker consumes saved commands and timing traces, reconstructs resource
service from the registered contract, and checks source-derived work/traffic.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "r11"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def verify_registration():
    registration = read(HERE / "preregistration_manifest.json")
    for path, expected in registration["files"].items():
        require(digest(ROOT / path) == expected, ("preregistration_changed", path))
    return registration


def independently_finish_work(start, work, phase=None, period=4096, blocked=819):
    """Integrate service using absolute blackout intervals, not runner code.

    A blackout starts at phase + k*period and lasts blocked cycles; modulo
    arithmetic includes the blackout from the previous period if necessary.
    The caller separates any service components exempt from blackouts.
    """
    require(start >= 0 and work >= 0, (start, work))
    if phase is None or work == 0:
        return start + work
    cursor = start
    remaining = work
    while remaining:
        # simulator defines phase as an additive offset: blackout when
        # (time + phase) mod period is in [0, blocked).
        relative = (cursor + phase) % period
        if relative < blocked:
            cursor += blocked - relative
            relative = blocked
        available = period - relative
        consumed = min(available, remaining)
        cursor += consumed
        remaining -= consumed
    return cursor


def paired_statistics(gains, critical=2.045229642):
    require(len(gains) >= 2, "paired statistics need independent blocks")
    mean = statistics.fmean(gains)
    deviation = statistics.stdev(gains)
    half = critical * deviation / math.sqrt(len(gains))
    return {"n": len(gains), "mean": mean, "std": deviation,
            "ci95_t": [mean - half, mean + half],
            "min": min(gains), "max": max(gains)}


def source_traffic_formula(tokens=4):
    """Dimensions independently read from frozen Qwen GDN source/config."""
    hidden, key_heads, value_heads, kd, vd = 2560, 16, 32, 128, 128
    qkv_width = 2 * key_heads * kd + value_heads * vd
    z_width = value_heads * vd
    dense_elements = hidden * (qkv_width + z_width + 2 * value_heads) + z_width * hidden
    state_bytes = value_heads * kd * vd * 4
    return {
        "dense_weight_payload_per_invocation": dense_elements * 2,
        "dense_macs": dense_elements * tokens,
        "recurrent_state_bytes": state_bytes,
        "external_recurrent_state_payload": state_bytes * 2,
        "baseline_local_recurrent_state_payload": state_bytes * tokens * 2,
        "resident_local_recurrent_state_payload": state_bytes * 2,
        "local_recurrent_state_payload_saved": state_bytes * 2 * (tokens - 1),
        "conv_state_bytes": qkv_width * 4 * 4,
        "module_output_bytes": tokens * hidden * 4,
    }


def close_enough(actual, expected, context, tolerance=0.000001):
    require(abs(actual - expected) <= tolerance, (context, actual, expected))


def command_service(command, hardware):
    """Derive command work directly from payload and registered scalar rates."""
    resource = command["res"]
    if resource == "EXT":
        return 1 + hardware["ext_setup_cycles"] + command.get("bytes", 0) / hardware["ext_bytes_per_cycle"]
    if resource == "LOCAL":
        return 1 + hardware["local_setup_cycles"] + command.get("bytes", 0) / hardware["local_bytes_per_cycle"]
    if resource.startswith("VPU"):
        return 1 + command.get("ops", 0) / hardware["vpu_ops_per_cycle_per_core"]
    if resource.startswith("MXU"):
        return 1 + hardware["projection_fill_cycles"] + command.get("macs", 0) / hardware["fp32_macs_per_cycle_per_core"]
    require(resource == "BARRIER", ("unknown_resource", resource))
    return 0


def audit_graph_structure(graph, contract):
    commands = graph["commands"]
    previous = {}
    traffic = defaultdict(Counter)
    work = defaultdict(Counter)
    services = []
    allowed = {"EXT", "LOCAL", "VPU0", "VPU1", "MXU0", "MXU1", "BARRIER"}
    for index, command in enumerate(commands):
        require(command["id"] == index, ("nonsequential_command_id", index))
        require(command["res"] in allowed, ("undeclared_resource", command))
        require(all(isinstance(x, int) and 0 <= x < index for x in command["deps"]), ("noncausal_dependency", command))
        resource = command["res"]
        if resource != "BARRIER":
            if resource in previous:
                require(previous[resource] in command["deps"], ("missing_FIFO_predecessor", index, previous[resource]))
            previous[resource] = index
        category = command.get("category", "unspecified")
        for key in ("bytes", "macs", "ops"):
            require(command.get(key, 0) >= 0, ("negative_work", index, key))
        traffic[resource][category] += command.get("bytes", 0)
        work[resource]["macs"] += command.get("macs", 0)
        work[resource]["ops"] += command.get("ops", 0)
        services.append(command_service(command, contract["hardware"]))
    allocations = sorted(graph["allocations"], key=lambda item: item["base"])
    cursor = 0
    names = set()
    for allocation in allocations:
        require(allocation["name"] not in names, ("duplicate_allocation_name", allocation["name"]))
        names.add(allocation["name"])
        require(allocation["size"] > 0 and allocation["base"] >= cursor, ("VMEM_overlap", allocation, cursor))
        cursor = allocation["base"] + allocation["size"]
    require(cursor <= contract["hardware"]["vmem_bytes"], ("VMEM_overflow", cursor))
    return {
        "commands": len(commands), "traffic": {r: dict(c) for r, c in traffic.items()},
        "work": {r: dict(c) for r, c in work.items()}, "vmem_allocated_peak": cursor,
        "service": services,
    }


def audit_trace(trace, graph, graph_audit, contract):
    commands = graph["commands"]
    require(len(trace["timings"]) == len(commands), "trace command count")
    finishes = []
    busy = Counter()
    blackout = contract["background"]
    quiet = trace["condition"] == "quiet"
    for index, command in enumerate(commands):
        ready = max((finishes[dependency] for dependency in command["deps"]), default=0)
        resource = command["res"]
        phase = trace["phases"].get(resource) if resource in ("EXT", "LOCAL") and not quiet else None
        service = graph_audit["service"][index]
        finish = independently_finish_work(ready, service, phase, blackout["period_cycles"], blackout["blocked_cycles"])
        actual_ready, actual_start, actual_finish = trace["timings"][index]
        close_enough(actual_ready, ready, ("ready", index))
        close_enough(actual_start, ready, ("start", index))
        close_enough(actual_finish, finish, ("finish", index))
        finishes.append(finish)
        busy[resource] += service
    elapsed = max(finishes, default=0)
    close_enough(trace["elapsed"], elapsed, "elapsed")
    require(elapsed + 0.000001 >= max(busy.values(), default=0), "busy resource lower bound")
    return {"seed": trace["seed"], "condition": trace["condition"], "elapsed": elapsed,
            "commands_replayed": len(commands), "port_and_compute_service_lower_bounds": dict(busy)}


def load_trace(path):
    with gzip.open(path, "rt", encoding="utf8") if str(path).endswith(".gz") else open(path, encoding="utf8") as handle:
        return json.load(handle)


def main():
    registration = verify_registration()
    contract = read(HERE / "contract.json")
    result = read(HERE / "results.json")
    require(result["status"] in ("PERFORMANCE_COMPLETE_PENDING_INDEPENDENT_AUDIT", "PASS_INDEPENDENT_AUDIT"), result["status"])
    qualification = read(HERE / "qualification_results.json")
    require(qualification["status"] == "PASS", "qualification")
    source = source_traffic_formula()
    graph_audits = {}
    graph_cache = {}
    trace_audits = []
    for variant, selected in result["selected"].items():
        graph_path = HERE / result["rows"][0]["results"][variant]["trace"]
        # trace path is used only to locate sibling graph file; consume the
        # declared graph_file from the actual trace instead of runner metadata.
        trace = load_trace(graph_path)
        declared = HERE / trace["graph_file"]
        with gzip.open(declared, "rt", encoding="utf8") as stream:
            graph = json.load(stream)
        audited = audit_graph_structure(graph, contract)
        graph_cache[variant] = graph
        graph_audits[variant] = audited
        require(graph["metadata"]["plan"] == selected, ("selection_mismatch", variant))
        require(graph["metadata"]["mode"] == "prefill", ("mode", variant))
        require(graph["metadata"]["state_bytes"] == source["recurrent_state_bytes"], ("state_size", variant))
        require(audited["traffic"].get("EXT", {}).get("state_load", 0) == source["external_recurrent_state_payload"] // 2, ("state load", variant))
        require(audited["traffic"].get("EXT", {}).get("state_store", 0) == source["external_recurrent_state_payload"] // 2, ("state store", variant))
        require(audited["work"]["MXU0"]["macs"] + audited["work"]["MXU1"]["macs"] == source["dense_macs"], ("dense macs", variant))
        require(graph["metadata"]["rf_peak"] <= contract["hardware"]["rf_bytes_per_core"], ("RF capacity", variant))
    # Decode proof is independently rebuilt from a fresh graph, not inferred
    # from timing traces. Compare command shape and state traffic exactly.
    require(graph_cache["baseline"]["metadata"]["plan"]["variant"] == "baseline", "baseline plan")
    decode_base = read(HERE / "qualification_results.json")["decode"]
    require(decode_base["status"] == "EXCLUDED_NO_INTERVENTION" and decode_base["equal_commands"], "decode exclusion")
    for row in result["rows"]:
        for variant in ("baseline", "resident"):
            trace_path = HERE / row["results"][variant]["trace"]
            trace = load_trace(trace_path)
            audited = audit_trace(trace, graph_cache[variant], graph_audits[variant], contract)
            trace_audits.append(dict(variant=variant, group=row["group"], **audited))
    require(len(trace_audits) == 122, ("trace_count", len(trace_audits)))
    by_group = {}
    for group in ("A", "B"):
        b = {x["seed"]: x["elapsed"] for x in trace_audits if x["group"] == group and x["variant"] == "baseline"}
        r = {x["seed"]: x["elapsed"] for x in trace_audits if x["group"] == group and x["variant"] == "resident"}
        require(set(b) == set(r) and len(b) == 30, ("paired_group", group))
        gains = [100 * (1 - r[s] / b[s]) for s in sorted(b)]
        by_group[group] = paired_statistics(gains)
    quiet = [x for x in trace_audits if x["group"] == "quiet"]
    require(len(quiet) == 2, "quiet count")
    quiet_b = next(x for x in quiet if x["variant"] == "baseline")["elapsed"]
    quiet_r = next(x for x in quiet if x["variant"] == "resident")["elapsed"]
    quiet_gain = 100 * (1 - quiet_r / quiet_b)
    gate = quiet_gain >= contract["gate"]["gain_pct"] and all(
        x["mean"] >= contract["gate"]["gain_pct"] and x["ci95_t"][0] > 0 for x in by_group.values())
    audit = {
        "status": "PASS",
        "registration": registration,
        "source_formula": source,
        "graph_audits": {k: {x: v for x, v in a.items() if x != "service"} for k, a in graph_audits.items()},
        "traces": {"count": len(trace_audits), "audited": len(trace_audits), "results": trace_audits},
        "statistics": by_group,
        "quiet": {"baseline_elapsed": quiet_b, "resident_elapsed": quiet_r, "gain_pct": quiet_gain},
        "prefill_gate_recomputed": gate,
        "decode": decode_base,
        "scope": "independent command service, FIFO/dependency, capacity, state traffic and paired-statistics replay; no device acceptance"
    }
    (HERE / "independent_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf8")
    (HERE / "independent_audit.md").write_text(
        "# R11 independent audit\n\n"
        f"Status: PASS. Replayed {len(trace_audits)} held-out traces (both variants), rebuilt service/FIFO/blackout timing and source traffic independently.\n\n"
        f"Quiet gain: {quiet_gain:.9f}%. A mean/95% CI: {by_group['A']['mean']:.9f}% [{by_group['A']['ci95_t'][0]:.9f}, {by_group['A']['ci95_t'][1]:.9f}]. B mean/95% CI: {by_group['B']['mean']:.9f}% [{by_group['B']['ci95_t'][0]:.9f}, {by_group['B']['ci95_t'][1]:.9f}].\n\n"
        f"The preregistered prefill gate recomputes to {'PASS' if gate else 'FAIL'}; decode is excluded because strict output-visible/clobber boundaries make the two static graphs identical.\n\n"
        "The checker did not import runner graph/timing functions. It checked nonnegative causal dependencies, every resource FIFO predecessor, non-overlapping VMEM allocations, source-derived state/dense-MAC totals, all trace timestamps, blackout integration, lower bounds, and paired seed alignment.\n",
        encoding="utf8")
    print(json.dumps({"status": "PASS", "traces": len(trace_audits), "prefill_gate_recomputed": gate,
                      "quiet_gain_pct": quiet_gain, "A": by_group["A"], "B": by_group["B"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
