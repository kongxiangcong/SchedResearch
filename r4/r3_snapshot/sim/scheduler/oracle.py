"""Exact tiny-DAG schedule oracle versus explicitly nonexact clairvoyant heuristic."""
from dataclasses import replace
from sim.compiler import compile_candidates, select_static
from sim.hardware_model import Hardware
from sim.workload import Workload
from sim.execution import simulate


def exact_orders(contract, durations, max_tasks=8):
    """Enumerate topological permutations, project resource orders, replay self-timed.

    Exact for this fixed-mapping, unary-resource, nonpreemptive model at zero overhead.
    Every feasible schedule induces a topological dispatch permutation; earliest replay
    of that permutation cannot be worse. Not an oracle for alternate placement/tiling.
    """
    tasks = {t.tid: t for t in contract.workload.tasks}
    if len(tasks) > max_tasks:
        raise ValueError("exact enumeration limited to tiny DAGs")
    predecessors = {x: {e.producer for e in contract.workload.edges if e.consumer == x} for x in tasks}
    best, best_contract, count = float("inf"), None, 0
    seen = set()
    def visit(prefix, pending):
        nonlocal best, best_contract, count
        if pending:
            for x in sorted(pending):
                if not predecessors[x] & pending:
                    visit(prefix + [x], pending - {x})
            return
        orders = {r: tuple(x for x in prefix if r in tasks[x].resources)
                  for t in tasks.values() for r in t.resources}
        key = tuple(sorted(orders.items()))
        if key in seen:
            return
        seen.add(key)
        candidate = replace(contract, resource_order=orders, admission_order=tuple(prefix))
        value = simulate(candidate, Hardware(window=max_tasks), durations, "A").latency
        count += 1
        if value < best:
            best, best_contract = value, candidate
    visit([], set(tasks))
    return best, best_contract, count


def clairvoyant_heuristic(contract, durations):
    actual = Workload(contract.workload.name, tuple(replace(t, predicted=durations[t.tid])
                      for t in contract.workload.tasks), contract.workload.edges, contract.workload.description)
    chosen = select_static(compile_candidates(actual), Hardware())
    return simulate(chosen, Hardware(), durations, "A")
