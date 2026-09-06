"""Exhaustive four-task admission/order probe and incremental dynamic control cost.

Run: python -X utf8 -B -m experiments.minimum_window
No real NPU calibration; exactness only covers this graph and two equiprobable worlds.
"""
from dataclasses import asdict, replace
import csv
import hashlib
import itertools
import json
from pathlib import Path
import statistics

from sim.compiler import candidates
from sim.execution import simulate, verify_trace
from sim.hardware_model import Hardware
from sim.workload.motifs import arrival_reversal


def all_contracts():
    base = candidates(arrival_reversal())[0]
    tasks = {task.tid: task for task in base.workload.tasks}
    result = []
    for sequence in itertools.permutations(tasks):
        positions = {task: i for i, task in enumerate(sequence)}
        if any(positions[e.producer] > positions[e.consumer] for e in base.workload.edges):
            continue
        resource_order = {r: tuple(x for x in sequence if r in tasks[x].resources)
                          for task in tasks.values() for r in task.resources}
        result.append(replace(base, admission_order=sequence, resource_order=resource_order))
    return result


WORLDS = (
    dict(load0=80, load1=120, vpu0=20, vpu1=20),
    dict(load0=120, load1=80, vpu0=20, vpu1=20),
)


def evaluate(contract, hardware, policy):
    results = [simulate(contract, hardware, durations, policy) for durations in WORLDS]
    for result in results:
        verify_trace(contract, result, hardware)
    return statistics.mean(result.latency for result in results), results


def main():
    directory = Path(__file__).resolve().parent / "results" / "minimum_window"
    directory.mkdir(parents=True, exist_ok=True)
    rows, traces = [], {}
    contracts = all_contracts()
    for window in (1, 2, 3, 4):
        for common_cost in (0, 1, 2):
            base_hw = Hardware(window=window, byte_window=4096, issue_width=1,
                               issue_cycle=common_cost, dispatch_latency=common_cost,
                               completion_latency=common_cost, wakeup_width=1,
                               wakeup_cycle=common_cost)
            scored = [(evaluate(c, base_hw, "A")[0], i, c) for i, c in enumerate(contracts)]
            static_latency, _, contract = min(scored, key=lambda x: (x[0], x[1]))
            for extra_dispatch in (0, 1, 2, 4, 8, 16):
                dynamic_hw = replace(base_hw, dispatch_latency=common_cost + extra_dispatch)
                dynamic_latency, dynamic_runs = evaluate(contract, dynamic_hw, "B")
                _, static_runs = evaluate(contract, base_hw, "A")
                row = dict(window=window, common_cost=common_cost,
                           extra_dynamic_dispatch=extra_dispatch,
                           static_expected=static_latency, dynamic_expected=dynamic_latency,
                           reduction_pct=100 * (static_latency - dynamic_latency) / static_latency,
                           static_state_bits=static_runs[0].metrics["abstract_state_bits"],
                           dynamic_state_bits=dynamic_runs[0].metrics["abstract_state_bits"],
                           descriptor_bytes=dynamic_runs[0].metrics["descriptor_bytes_estimate"],
                           exhaustive_static_contracts=len(contracts),
                           admission="|".join(contract.admission_order))
                rows.append(row)
                if common_cost == 0 and extra_dispatch in (0, 8):
                    key = f"window{window}_extra{extra_dispatch}"
                    traces[key] = {"A": [r.trace for r in static_runs],
                                   "B": [r.trace for r in dynamic_runs],
                                   "static_hardware": asdict(base_hw),
                                   "dynamic_hardware": asdict(dynamic_hw)}
    with (directory / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    artifact = {"evidence": "exact finite synthetic distribution; no device timing or area claim",
                "scope": "all topological admission permutations and projected static resource orders; fixed mapping and addresses",
                "fairness": "B uses A-optimal frozen contract; same common costs, plus explicit dynamic-only extra dispatch cost",
                "state": "partial logical bit model; graph history and notification storage included, not RTL PPA",
                "worlds": WORLDS, "results": rows, "traces": traces}
    (directory / "results.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    source_root = directory.parents[2]
    sources = sorted((source_root / "sim").rglob("*.py")) + [Path(__file__)]
    manifest = {"command": "python -X utf8 -B -m experiments.minimum_window",
                "source_sha256": {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sources}, "rows": len(rows)}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        if row["common_cost"] == 0 and row["extra_dynamic_dispatch"] in (0, 4, 8):
            print(row)


if __name__ == "__main__":
    main()
