"""Reproduce R2 without changing its source; demonstrate two bounded counterexamples.

Run from the repository root: python -B -X utf8 analysis/evidence/audit_r2.py
Only the JSON next to this script is written. No external compiler is accessed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "r2-ooo-npu" / "toy-sim" / "r4sim.py"


def priority(module, tasks):
    for task in reversed(module.topo(tasks)):
        task.prio = task.mean + max((tasks[i].prio for i in task.succs), default=0)


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location("r2_audit_original", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    rows = []
    configs = [
        (4, 2, True, 0.6, 0, False),
        (4, 2, True, 0.6, 0.05, False),
        (4, 2, True, 0.6, 0, True),
        (4, 2, True, 0.6, 0.05, True),
        (8, 2, True, 0.6, 0.05, True),
        (32, 8, False, 0.6, 0, False),
        (32, 8, False, 0.6, 0.05, True),
    ]
    for streams, cores, shared, cov, tail, couple in configs:
        for reuse in (0, 0.5, 1):
            dma_only = not (tail or couple)
            st, lane, sa, gain_st, gain_lane = module.run(
                streams, cores, shared, cov, reuse, trials=200,
                tail_p=tail, couple=couple, dma_only=dma_only,
            )
            rows.append(dict(
                streams=streams, cores=cores, shared_dma=shared, cov=cov,
                tail_probability=tail, couple=couple, reuse=reuse,
                dma_only=dma_only, trials=200, latency_seed=1,
                reuse_graph_seed=7, ST=st, lane_ST=lane, SA=sa,
                latency_reduction_vs_ST_percent=gain_st,
                latency_reduction_vs_lane_percent=gain_lane,
            ))

    # Equal-probability, bounded timing scenarios; all edges are true data edges.
    # The two possible fixed VPU orders exhaust the static scheduling choices.
    tasks = [
        module.Task(0, "load", "dma0", 100, succs={2}),
        module.Task(1, "load", "dma1", 100, succs={3}),
        module.Task(2, "comp", "vpu0", 20, preds={0}),
        module.Task(3, "comp", "vpu0", 20, preds={1}),
    ]
    priority(module, tasks)
    case_rows = []
    for first, second in ((80, 120), (120, 80)):
        durations = {0: first, 1: second, 2: 20, 3: 20}
        for order in ([2, 3], [3, 2]):
            fixed = {"dma0": [0], "dma1": [1], "vpu0": order}
            case_rows.append(dict(
                durations=durations, probability=0.5,
                vpu_order=order,
                fixed_makespan=module.simulate(tasks, durations, fixed),
                completion_ready_makespan=module.simulate(tasks, durations),
            ))
    expectations = []
    for order in ([2, 3], [3, 2]):
        expectations.append(dict(
            vpu_order=order,
            expected_fixed_makespan=statistics.mean(
                x["fixed_makespan"] for x in case_rows if x["vpu_order"] == order
            ),
        ))
    assert [x["expected_fixed_makespan"] for x in expectations] == [150, 150]
    assert all(x["completion_ready_makespan"] == 140 for x in case_rows)

    # Same logical DAG, equal completion timestamps, changed producer numbering.
    # Both producers finish at 10; X has high-priority H(10)->Y(100), and L(100).
    tie_rows = []
    for high_first in (False, True):
        high_parent, low_parent = (0, 1) if high_first else (1, 0)
        tie_tasks = [
            module.Task(0, "load", "p0", 10),
            module.Task(1, "load", "p1", 10),
            module.Task(2, "comp", "X", 100, preds={low_parent}),
            module.Task(3, "comp", "X", 10, preds={high_parent}, succs={4}),
            module.Task(4, "comp", "Y", 100, preds={3}),
        ]
        tie_tasks[high_parent].succs = {3}
        tie_tasks[low_parent].succs = {2}
        priority(module, tie_tasks)
        durations = {t.tid: t.mean for t in tie_tasks}
        correct_order = {"p0": [0], "p1": [1], "X": [3, 2], "Y": [4]}
        tie_rows.append(dict(
            high_priority_parent_has_lower_id=high_first,
            original_dynamic_makespan=module.simulate(tie_tasks, durations),
            original_static_list_order=module.static_list_schedule(tie_tasks),
            feasible_batch_completion_order_makespan=module.simulate(
                tie_tasks, durations, correct_order
            ),
        ))
    assert [x["original_dynamic_makespan"] for x in tie_rows] == [220, 120]
    assert all(x["feasible_batch_completion_order_makespan"] == 120 for x in tie_rows)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash

    output = dict(
        date="2026-09-05", evidence_level="uncalibrated synthetic event model",
        source="r2-ooo-npu/toy-sim/r4sim.py", source_sha256=source_hash,
        source_unchanged=True, r2_table_b1_reproduction=rows,
        no_reuse_bounded_uncertainty=dict(
            task_count=4, buffer_aliasing=False, physical_address_reassignment=False,
            dma_cov=0.2, dma_mean=100, dma_distribution="two-point bounded, anticorrelated",
            scenarios=case_rows, fixed_order_expectations=expectations,
            optimal_fixed_expected_makespan=150,
            ready_expected_makespan=140,
            latency_reduction_percent=(150-140)/150*100,
            speedup=150/140,
            significance="Existence counterexample; not a measured workload or NPU benefit.",
        ),
        simultaneous_completion_id_bias=tie_rows,
    )
    output_path = Path(__file__).with_name("r2_audit_results.json")
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output_path), source_unchanged=True,
                         reproduced_rows=len(rows), no_reuse_fixed=150, no_reuse_ready=140,
                         id_bias_original=[220,120]), ensure_ascii=False))


if __name__ == "__main__":
    main()
