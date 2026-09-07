"""Train-only resource-order local search; validation-only final selection."""
from dataclasses import replace
import copy
import random
import statistics
from r4.engine import simulate, Environment
from sim.compiler import candidates
from sim.workload import topology


def optimize(prepared, train, validation, budget=128):
    c = prepared.contract
    variants = candidates(c.workload, random_count=20)
    options, pool8, poolall = {}, [], []
    nominal = Environment(999999, 'deterministic')
    for i, variant in enumerate(variants):
        pp = copy.copy(prepared)
        pp.contract = replace(c, priority=variant.priority)
        trial = simulate(pp, nominal, 'B', detailed=True)
        order = tuple(x['task'] for x in trial['trace'])
        if order not in options:
            options[order] = statistics.mean(simulate(prepared, e, 'A', order=order)['latency'] for e in train)
            poolall.append(order)
        if i < 8 and order not in pool8:
            pool8.append(order)
    edges = [(e.producer, e.consumer) for e in c.workload.edges]

    def legal(order):
        pos = {x: i for i, x in enumerate(order)}
        return all(pos[a] < pos[b] for a, b in edges)

    # A reproducible bounded adjacent/move neighborhood, seeded from the four
    # strongest pool plans. Every candidate preserves the exact memory DAG.
    rng = random.Random(1471)
    frontier = sorted(poolall, key=lambda o: (options[o], o))[:4]
    evaluated, improvements, restarts, exhausted = 0, 0, 0, False
    visited = set(options)
    while frontier and evaluated < budget:
        current = frontier.pop(0)
        restarts += 1
        neighbors = []
        for i in range(len(current)):
            for delta in (-4, -2, -1, 1, 2, 4):
                j = i + delta
                if 0 <= j < len(current):
                    new = list(current)
                    new.insert(j, new.pop(i))
                    order = tuple(new)
                    if order not in visited and legal(order):
                        visited.add(order); neighbors.append(order)
        rng.shuffle(neighbors)
        best = current
        for order in neighbors:
            if evaluated >= budget:
                break
            score = statistics.mean(simulate(prepared, e, 'A', order=order)['latency'] for e in train)
            options[order] = score
            evaluated += 1
            if score < options[best] - 1e-9:
                best = order
        if best != current:
            improvements += 1
            frontier.insert(0, best)
    exhausted = evaluated >= budget
    # Validation cannot influence exploration. Select among top 8 training
    # candidates AND all original pool candidates to protect the incumbent.
    finalists = list(dict.fromkeys(sorted(options, key=lambda o: (options[o], o))[:8] + poolall))
    val = {o: statistics.mean(simulate(prepared, e, 'A', order=o)['latency'] for e in validation) for o in finalists}
    selected = min(finalists, key=lambda o: (val[o], options[o], o))
    old = min(pool8, key=lambda o: (options[o], o))
    best_train = min(options, key=lambda o: (options[o], o))
    return selected, old, {'search': 'resource-order projection of legal topological insertion/swap search',
        'training_seeds': [e.seed for e in train], 'validation_seeds': [e.seed for e in validation],
        'nominal_pool_unique': len(poolall), 'old_8_pool_unique': len(pool8),
        'local_evaluations': evaluated, 'search_budget': budget, 'budget_exhausted': exhausted,
        'improving_neighborhoods': improvements, 'neighborhoods_started': restarts,
        'best_training_mean': options[best_train], 'selected_training_mean': options[selected],
        'selected_validation_mean': val[selected], 'old_pool_training_mean': options[old],
        'selected_order': selected, 'old_pool_order': old,
        'candidates': [{'order': o, 'training_mean': score, 'validation_mean': val.get(o)} for o, score in options.items()],
        'claim': 'bounded local search; not globally optimal full-graph schedule or production compiler'}
