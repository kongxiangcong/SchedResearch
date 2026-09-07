"""Independent audit adversaries and tiny exact enumeration against the engine.

Only this fixture producer imports model. independent_check.py never does.
"""
from copy import deepcopy
import argparse
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from r9.independent_check import audit_trace, check_address_hazards, check_nonoverlap, digest, require, same
from r9.model import build_graph, load_hardware, simulate


def envelope(hardware, config, environment):
    graph = build_graph(hardware, config)
    return {"hardware": hardware, "graph": graph, "config": graph["config"], "environment": environment,
            "result": simulate(graph, hardware, environment, detailed=True)}


def reject(label, expected, function):
    try:
        function()
    except AssertionError as error:
        require(expected in str(error), f"{label}: unexpected rejection {error}")
        return {"name": label, "status": "DETECTED", "reason": str(error)}
    raise AssertionError(f"corruption undetected: {label}")


def region(space, owner, address, size):
    return {"space": space, "owner": owner, "address": address, "size": size}


def tiny_graph(hardware):
    reserve = hardware["vmem_reserved_bytes_per_core"]
    a0, a1 = region("vmem", 0, reserve, 64), region("vmem", 1, reserve, 64)
    b0 = region("vmem", 0, reserve + 64, 128)
    nodes = []
    for priority, (name, source, destinations) in enumerate((
            ("a", region("ext_x", -1, 0, 64), [a0, a1]),
            ("b", region("ext_w", -1, 0, 128), [b0]))):
        nodes.append({"id": name, "kind": "dma_read", "cluster": 0, "priority": priority, "deps": [],
                      "reads": [source], "writes": destinations,
                      "packets": [{"id": name + ":p", "logical_bytes": source["size"], "external_bytes": source["size"],
                                   "local_bytes": sum(r["size"] for r in destinations), "source_spans": [source],
                                   "destination_spans": destinations}]})
    return {"scope": "tiny", "config": {"outstanding": 2}, "allocations": [a0, a1, b0],
            "nodes": nodes, "output_nodes": ["a", "b"], "external_bytes": 192,
            "cluster_dma_bytes": [256], "core_cycles": [0, 0]}


def tiny_expected(order, phase):
    """Enumerate integer service ticks; independent from both simulator and checker integrals."""
    ext_time, local_time, visible = 12, 0, {}
    for name in order:
        work = {"a": 1, "b": 2}[name]
        remaining = work
        while remaining:
            if (ext_time - phase) % 32 >= 8:
                remaining -= 1
            ext_time += 1
        local_time = max(local_time, ext_time) + 2
        visible[name] = local_time + 4
    return max(visible.values()), visible


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=ROOT / "r9/results")
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    hw = load_hardware()
    environment = {"period": 8192, "duty": .35, "phase": 1234}
    reports = []
    for mapping, layout, multicast, resident in itertools.product(
            ("C1N", "C2N", "C2K"), ("gather", "row"), (False, True), (False, True)):
        config = {"mapping": mapping, "layout": layout, "multicast": multicast, "resident_x": resident}
        example = envelope(hw, config, environment)
        reports.append({"config": example["config"], **audit_trace(example)})
    for mapping in ("C1N", "C2N", "C2K"):
        example = envelope(hw, {"mapping": mapping, "ktile": 0, "buffers": 1, "prefetch": 1, "resident_x": True}, environment)
        reports.append({"config": example["config"], **audit_trace(example)})
    example = envelope(hw, {"mapping": "C2K"}, environment)
    broken = deepcopy(example)
    broken["result"]["requests"].pop()
    corruptions = [reject("missed_payload", "request coverage", lambda: audit_trace(broken))]
    broken = deepcopy(example)
    op = broken["result"]["operations"][0]
    duration = op["end"] - op["start"]
    op["start"], op["end"] = 0, duration
    corruptions.append(reject("early_consumer", "early consumer", lambda: audit_trace(broken)))
    broken = deepcopy(example)
    packet = next(p for n in broken["graph"]["nodes"] for p in n.get("packets", []) if p["local_bytes"] > p["logical_bytes"])
    packet["local_bytes"] = packet["logical_bytes"]
    corruptions.append(reject("free_multicast_delivery", "altered local_bytes", lambda: audit_trace(broken)))
    broken = deepcopy(example)
    broken["result"]["requests"][0]["external_segments"][0][1] -= 1
    corruptions.append(reject("missed_service_bytes", "external segment endpoints", lambda: audit_trace(broken)))
    # Focused interval corruptions isolate the safety property; their other event
    # fields are intentionally absent rather than malformed distractors.
    region0 = region("vmem", 0, hw["vmem_reserved_bytes_per_core"], 64)
    corruptions.append(reject("alias_overwrite_during_last_reader", "address hazard", lambda:
                              check_address_hazards([(10, 20, "read", "dma_source", region0),
                                                     (15, 25, "write", "refill", region0)])))
    corruptions.append(reject("credit_overflow", "capacity 4 exceeded", lambda:
                              check_nonoverlap([(0, 10, i) for i in range(5)], "outstanding/credit", 4)))
    corruptions.append(reject("transport_slot_reuse", "capacity 1 exceeded", lambda:
                              check_nonoverlap([(0, 10, "a"), (5, 15, "b")], "transport slot", 1)))
    # Exact legal two-chain instance: both read requests are accepted at t=0.
    # A multicasts 64B to two VMEMs, B unicasts 128B; EXT orders AB and BA exhaust
    # all choices. Local order follows EXT destination arrival; no further choice.
    tiny_hw = {**hw, "clusters": 1}
    graph = tiny_graph(tiny_hw)
    tiny_rows = []
    for phase, order in itertools.product((0, 13), itertools.permutations(("a", "b"))):
        env = {"period": 32, "duty": .25, "phase": phase}
        intervention = {"decision_index": 0, "choose_request": order[0] + ":p", "cost_cycles": 0}
        result = simulate(graph, tiny_hw, env, detailed=True, intervention=intervention)
        expected, completions = tiny_expected(order, phase)
        require(same(result["elapsed"], expected), "tiny exact final discrepancy")
        require(all(same(result["node_completion"][name], value) for name, value in completions.items()), "tiny exact completion discrepancy")
        full = {"hardware": tiny_hw, "graph": graph, "config": graph["config"], "environment": env, "result": result}
        audit = audit_trace(full)
        tiny_rows.append({"phase": phase, "order": list(order), "independent_elapsed": expected,
                          "independent_completions": completions, "audit": audit, "envelope": full})
    tiny_report = {"status": "PASS", "scope": "exhaustive two accepted read request stage chains; destination VMEM visible endpoint, not main Y endpoint",
                   "legal_external_orders": 2, "phases": [0, 13], "cases": tiny_rows,
                   "enumeration_reason": "Two initially eligible requests, one shared EXT server, FIFO local stage; first EXT choice determines the only remaining order.",
                   "minimum_elapsed_by_phase": {str(phase): min(row["independent_elapsed"] for row in tiny_rows if row["phase"] == phase) for phase in (0, 13)}}
    (args.results / "tiny_exact_results.json").write_text(json.dumps(tiny_report, indent=2), encoding="utf8")
    report = {"status": "PASS", "scope": "reference-model structural tests and deliberately corrupted evidence only; no target runs",
              "checker_sha256": digest(ROOT / "r9/independent_check.py"), "test_sha256": digest(__file__),
              "model_sha256": digest(ROOT / "r9/model.py"), "smoke_configurations": len(reports),
              "smoke_requests": sum(row["requests"] for row in reports), "smoke": reports,
              "corruption_fixtures": corruptions, "tiny_exact_cases": len(tiny_rows)}
    (args.results / "audit_tests.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("smoke", "corruption_fixtures")}))


if __name__ == "__main__":
    main()
