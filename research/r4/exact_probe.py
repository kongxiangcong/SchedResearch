"""Exact finite-distribution static gap for seven source-derived FFN tile tasks."""
from dataclasses import replace, asdict
from pathlib import Path
import itertools
import json
import statistics
from r4.graph import Case
from r4.qwen_lowering import build_full
from r4.lowering import lower, Target, fixed_order
from r4.engine import Environment, Prepared, simulate
from r4.static_search import optimize


class TwoPoint(Environment):
    def factor(self, task):
        if task.tid == 'load.pack.ffn_gu0':
            return (0.5, 1.5)[self.seed]
        if task.tid == 'load.pack.ffn_gu1':
            return (1.5, 0.5)[self.seed]
        return 1.0


def main():
    base = build_full()
    values = base.evaluate()
    keep = ['ffn_gu0', 'ffn_swiglu0', 'ffn_gu1', 'ffn_swiglu1']
    nodes = [n for n in base.nodes if n.name in keep]
    writers = {x for n in nodes for x in n.writes}
    reads = {x for n in nodes for x in n.reads}
    initial = {x: values[x] for x in reads - writers}
    outputs = ('ffn_act0', 'ffn_act1')
    case = Case('qwen_source_ffn_two_tiles_exact', initial, nodes, outputs,
                {x: values[x] for x in outputs}, {'scope': 'FFN gate/up+SwiGLU two intermediate tiles; scaled, activation and packed weights are explicit DMA'})
    contract, info = lower(case)
    hw = replace(Target().hardware(), issue_cycle=0, dispatch_latency=0,
                 completion_latency=0, wakeup_cycle=0)
    pp = Prepared(contract, hw)
    pred = {t.tid: set() for t in contract.workload.tasks}
    for e in contract.workload.edges:
        pred[e.consumer].add(e.producer)
    orders = []
    def visit(order, left):
        if not left:
            orders.append(tuple(order)); return
        for x in sorted(left):
            if pred[x] <= set(order):
                visit(order+[x], left-{x})
    visit([], set(pred))
    unique = {}
    for order in orders:
        c = fixed_order(contract, order)
        signature = tuple(sorted(c.resource_order.items()))
        unique.setdefault(signature, order)
    envs = [TwoPoint(0), TwoPoint(1)]
    rows = []
    for order in unique.values():
        times = [simulate(pp, e, 'A', order=order)['latency'] for e in envs]
        rows.append({'order': order, 'scenarios': times, 'mean': statistics.mean(times)})
    best = min(rows, key=lambda r: (r['mean'], r['order']))
    selected, old, search = optimize(pp, envs, envs, budget=128)
    heuristic = statistics.mean(simulate(pp, e, 'A', order=selected)['latency'] for e in envs)
    dynamic = [simulate(pp, e, 'B', order=best['order'], detailed=True) for e in envs]
    oracle = [min(r['scenarios'][i] for r in rows) for i in range(2)]
    result = {'scope': 'exact over all legal unary resource orders, zero control cost/full admission, specified equiprobable two-point external demand; no calendar',
        'workload': asdict(contract.workload), 'target': asdict(Target()), 'hardware': asdict(hw),
        'topological_orders': len(orders), 'unique_resource_orders': len(rows),
        'distribution': 'pack0/pack1 demand factors (0.5,1.5) or (1.5,0.5), P=1/2; all other demand fixed',
        'optimal_static': best, 'clairvoyant_optimum_each_scenario': oracle,
        'clairvoyant_mean': statistics.mean(oracle), 'B_mean': statistics.mean(r['latency'] for r in dynamic),
        'search_mean': heuristic, 'search_exact_gap_pct': 100*(heuristic/best['mean']-1),
        'rows': rows, 'dynamic_traces': dynamic, 'search': search,
        'split_note': 'Exact finite distribution calculation intentionally uses both exhaustive scenarios; not a held-out empirical generalization experiment.'}
    path = Path('experiments/results/r4/exact_probe.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print({k: result[k] for k in ('topological_orders','unique_resource_orders','optimal_static','B_mean','clairvoyant_mean','search_exact_gap_pct')})


if __name__ == '__main__':
    main()
