"""Independent R4 checks; no simulator event-loop implementation is reused here.

Checks here validate the declared mathematical/abstract contract, never real
model quality, a production compiler, RTL, or silicon behavior.
"""
from __future__ import annotations

import hashlib
import math
import random
from typing import Any

import numpy as np


def check_case_orders(case: Any, count: int = 20) -> dict:
    """Execute independently randomized source-DAG orders and check every output.

    The expected arrays must come from the model agent's independent reference;
    executing the graph itself once does not manufacture expected results.
    """
    nodes = {n.name: n for n in case.nodes}
    assert len(nodes) == len(case.nodes), "duplicate source node"
    writers = {}
    for n in case.nodes:
        assert n.source, f"missing source reference: {n.name}"
        assert len(n.writes) == len(set(n.writes)), f"duplicate write: {n.name}"
        for key in n.writes:
            assert key not in writers and key not in case.initial, f"SSA violation: {key}"
            writers[key] = n.name
    dependencies = {}
    for n in case.nodes:
        assert all(k in writers or k in case.initial for k in n.reads), f"undefined input: {n.name}"
        dependencies[n.name] = {writers[k] for k in n.reads if k in writers}
        assert n.name not in dependencies[n.name], f"self dependency: {n.name}"
    assert set(case.outputs) <= set(case.reference), "reference omits externally visible output"
    initial_hash = {k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in case.initial.items()}
    errors, unique_orders = [], set()
    for seed in range(count):
        rng = random.Random(70000 + seed)
        pending, done, order = set(nodes), set(), []
        values = {k: v.copy() for k, v in case.initial.items()}
        while pending:
            ready = sorted(n for n in pending if dependencies[n] <= done)
            assert ready, "source DAG cycle"
            name = rng.choice(ready)
            node = nodes[name]
            # A declared reader must not mutate producer/constant storage.
            old = {k: values[k].copy() for k in node.reads}
            result = node.run(*(values[k] for k in node.reads))
            for key, before in old.items():
                np.testing.assert_array_equal(values[key], before, err_msg=f"undeclared in-place write {name}:{key}")
            results = (result,) if len(node.writes) == 1 else result
            assert len(results) == len(node.writes)
            for key, value in zip(node.writes, results):
                values[key] = np.asarray(value)
                assert np.isfinite(values[key]).all(), f"nonfinite tensor: {key}"
            done.add(name)
            pending.remove(name)
            order.append(name)
        unique_orders.add(tuple(order))
        for key in case.outputs:
            actual, expected = values[key], case.reference[key]
            assert actual.shape == expected.shape, f"shape mismatch: {key}"
            np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-6, err_msg=f"{case.name}:{key}:seed={seed}")
            errors.append(float(np.max(np.abs(actual - expected))))
    assert initial_hash == {k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in case.initial.items()}, "initial arrays mutated"
    return {"case": case.name, "orders_executed": count, "distinct_legal_orders": len(unique_orders),
            "outputs_checked": list(case.outputs), "max_absolute_error": max(errors, default=0.0),
            "scope": "random-weight mathematical source DAG; not device numerical precision or quality"}


def check_alias_two_readers() -> dict:
    """Negative contract: new owner must wait for BOTH old-buffer readers."""
    from dataclasses import replace
    from sim.compiler import Contract
    from sim.hardware_model import Hardware
    from sim.memory import Buffer
    from sim.workload import Edge, Task, Workload

    tasks = tuple(Task(n, "compute", (n,), 1, output_bytes=64) for n in ("p", "a", "b", "w"))
    edges = (Edge("p", "a"), Edge("p", "b"), Edge("a", "w", "WAR"))
    graph = Workload("redteam_two_readers", tasks, edges, "old writer has two readers")
    buffers = (Buffer("p", "cluster0", 0, 64, ("a", "b")),
               Buffer("a", "cluster0", 64, 64, ()),
               Buffer("b", "cluster0", 128, 64, ()),
               Buffer("w", "cluster0", 0, 64, ()))
    contract = Contract(graph, buffers, {n.tid: 0 for n in tasks}, ("p", "a", "b", "w"), {})
    rejected = False
    try:
        contract.validate(Hardware(memory_capacity=192))
    except ValueError as e:
        rejected = "unsafe alias" in str(e)
    assert rejected, "alias accepted despite missing second reader edge"
    valid = replace(contract, workload=replace(graph, edges=edges + (Edge("b", "w", "WAR"),)))
    valid.validate(Hardware(memory_capacity=192))
    return {"missing_second_reader": "rejected", "both_readers": "accepted"}


def check_tensor_contract(case: Any, contract: Any, info: dict) -> dict:
    """Check packed byte spans, source read provenance, and boundary live-outs."""
    task_map = {t.tid: t for t in contract.workload.tasks}
    buffers = {b.owner: b for b in contract.buffers}
    edge_pairs = {(e.producer, e.consumer) for e in contract.workload.edges}
    succ = {x: set() for x in task_map}
    for e in contract.workload.edges:
        succ[e.producer].add(e.consumer)

    def successors(start):
        seen, work = set(), list(succ[start])
        while work:
            node = work.pop()
            if node not in seen:
                seen.add(node)
                work.extend(succ[node])
        return seen

    for key, tensor in info['tensors'].items():
        b = buffers[tensor['writer']]
        expected_width = case.metadata.get('storage_bytes', {}).get(key, 2)
        assert tensor['storage_element_bytes'] == expected_width, f"undeclared storage width: {key}"
        assert tensor['bytes'] == int(np.prod(tensor['shape'])) * tensor['storage_element_bytes'], f"tensor bytes: {key}"
        assert b.address <= tensor['address'] and tensor['address'] + tensor['bytes'] <= b.address + b.size, f"tensor outside pack: {key}"
        for consumer in tensor['readers']:
            assert (tensor['writer'], consumer) in edge_pairs, f"missing producer-read edge: {key}->{consumer}"
    for owner, keys in info['task_tensors'].items():
        spans = sorted((info['tensors'][key]['address'], info['tensors'][key]['address'] + info['tensors'][key]['bytes']) for key in keys)
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), f"same-task outputs overlap: {owner}"
    liveout_owners = {info['tensors'][key]['writer'] for key in case.outputs}
    for owner in liveout_owners:
        old = buffers[owner]
        later = successors(owner)
        for name in later:
            new = buffers[name]
            if old.domain == new.domain:
                assert max(old.address, new.address) >= min(old.address + old.size, new.address + new.size), f"boundary live-out overwritten: {owner}->{name}"
    scratch = case.metadata.get('internal_scratch', {})
    for node, internal in scratch.items():
        annotation = info['annotations'][node]
        core = annotation['fixed_core']
        reserved = info['internal_scratch_bytes_by_core'].get(core, info['internal_scratch_bytes_by_core'].get(str(core), 0))
        assert reserved >= internal['bytes'], f"internal scratch unreserved: {node}"
        expected_sram = (annotation['read_bytes'] + annotation['write_bytes'] + internal['traffic_bytes']) / info['target']['sram_bytes_cycle_per_port']
        assert abs(annotation['sram_demand'] - expected_sram) < 1e-9, f"internal traffic uncharged: {node}"
    reserved_total = sum(max(64, (b + 63) // 64 * 64) for b in info.get('internal_scratch_bytes_by_core', {}).values() if b)
    assert all(b.address >= reserved_total for b in contract.buffers), 'ordinary tensor aliases reserved internal scratch'
    return {"tensor_count": len(info['tensors']), "liveout_buffer_count": len(liveout_owners),
            "span_provenance_and_liveouts": "passed", "scope": "declared byte width; not physical dtype conversion"}


def check_trace(contract: Any, result: dict, order: tuple | list) -> dict:
    """Replay visibility, ports, SRAM ownership and calendar integral from trace."""
    tasks = {t.tid: t for t in contract.workload.tasks}
    rows = result['trace']
    byid = {r['task']: r for r in rows}
    assert len(rows) == len(tasks) and set(byid) == set(tasks), "lost/duplicate task"
    hw, env = result['hardware'], result['environment']
    eps = 1e-7

    def close(a, b, what):
        assert abs(a - b) <= eps * max(1, abs(a), abs(b)), f"{what}: {a}!={b}"

    issue_free = [0.] * hw['issue_width']
    issue_releases = []
    for r in rows:
        lane = min(range(len(issue_free)), key=issue_free.__getitem__)
        assert r['dispatch'] >= issue_free[lane] - eps, "issue bandwidth exceeded"
        issue_free[lane] = r['dispatch'] + hw['issue_cycle']
        issue_releases.append(issue_free[lane])
        close(r['start'], r['dispatch'] + hw['dispatch_latency'], 'dispatch latency')
        assert r['finish'] > r['start'], "nonpositive service"
        assert set(r['resources']) == set(tasks[r['task']].resources), "mapping changed"
        close(r['nominal_work'], tasks[r['task']].predicted, 'nominal demand changed')
        expected_factor = 1.
        if tasks[r['task']].kind == 'memory' and env['mode'] in ('service', 'combined'):
            digest = hashlib.sha256(f"{env['seed']}:{r['task']}".encode()).digest()
            u = random.Random(int.from_bytes(digest[:8], 'big')).random()
            expected_factor += env['amplitude'] * (2 * u - 1)
        close(r['external_factor'], expected_factor, 'external service draw changed')
        if tasks[r['task']].kind != 'memory':
            close(r['external_factor'], 1., 'compute randomized')
            close(r['finish'] - r['start'], tasks[r['task']].predicted, 'compute duration')
        elif env['mode'] in ('calendar', 'combined'):
            # Closed-form periodic service integral, not the simulator's loop.
            period, busy = env['period'], env['period'] * env['busy_fraction']
            phase = random.Random(env['seed'] + 937).random() * period
            def busy_prefix(t):
                n = math.floor((t + phase) / period)
                remainder = (t + phase) - n * period
                return n * busy + min(remainder, busy)
            busy_time = busy_prefix(r['finish']) - busy_prefix(r['start'])
            integrated = r['finish'] - r['start'] - (1 - env['busy_rate']) * busy_time
            close(integrated, r['nominal_work'] * r['external_factor'], 'calendar service conservation')
            segments = r['calendar_segments']
            assert segments, 'missing calendar segments'
            close(segments[0][0], r['start'], 'calendar begin')
            close(segments[-1][1], r['finish'], 'calendar end')
            for a, b in zip(segments, segments[1:]):
                close(a[1], b[0], 'calendar contiguous')
            for a, b, rate in segments:
                expected = env['busy_rate'] if ((a + b) / 2 + phase) % period < busy else 1.
                # The event engine may nudge a floating boundary by 1e-8 cycles.
                # Global service conservation is still checked above; do not
                # interpret a sub-tolerance nudge as a physical service segment.
                if b - a > eps:
                    close(rate, expected, 'calendar rate')
        else:
            close(r['finish'] - r['start'], r['nominal_work'] * r['external_factor'], 'service conservation')

    notices = result['notifications']
    assert len(notices) == len(contract.workload.edges), "lost/duplicate notification"
    assert {n['edge'] for n in notices} == set(range(len(contract.workload.edges)))
    wake_free = [0.] * hw['wakeup_width']
    deliveries = {}
    for n in notices:
        edge = contract.workload.edges[n['edge']]
        assert (n['producer'], n['consumer']) == (edge.producer, edge.consumer)
        close(n['completion_time'], byid[edge.producer]['finish'], 'notification completion')
        close(n['enqueue'], n['completion_time'] + hw['completion_latency'], 'notification enqueue')
        lane = min(range(len(wake_free)), key=wake_free.__getitem__)
        expected = max(n['enqueue'], wake_free[lane])
        close(n['delivery'], expected, 'wakeup queue replay')
        wake_free[lane] = expected + hw['wakeup_cycle']
        deliveries[n['edge']] = n['delivery']
        assert byid[edge.consumer]['dispatch'] >= n['delivery'] - eps, 'dependency issued before actual wakeup delivery'

    admission = {a['task']: a for a in result['admissions']}
    assert len(admission) == len(tasks)
    assert [a['task'] for a in result['admissions']] == list(order), 'admission sequence mismatch'
    for name, r in byid.items():
        a = admission[name]
        close(r['admitted'], a['time'], 'admitted metadata')
        assert a['time'] <= r['dispatch'] + eps
        incoming = [deliveries[i] for i, e in enumerate(contract.workload.edges) if e.consumer == name]
        close(r['ready'], max([a['time']] + incoming), 'admitted-ready timestamp')
    from sim.metrics import descriptor_size
    for name, a in admission.items():
        close(a['bytes'], descriptor_size(tasks[name], sum(e.consumer == name for e in contract.workload.edges)), 'descriptor bytes')
    peak_count, peak_bytes = 0, 0
    for at in sorted({a['time'] for a in admission.values()} | {r['finish'] for r in rows}):
        active = [name for name, a in admission.items() if a['time'] <= at + eps and byid[name]['finish'] > at + eps]
        total = sum(admission[name]['bytes'] for name in active)
        assert len(active) <= hw['window'] and total <= hw['byte_window'], 'admission capacity exceeded'
        peak_count, peak_bytes = max(peak_count, len(active)), max(peak_bytes, total)
    close(peak_count, result['metrics']['window_peak'], 'window peak')
    close(peak_bytes, result['metrics']['descriptor_bytes_peak'], 'byte window peak')

    resource_orders = {resource: [name for name in order if resource in tasks[name].resources]
                       for t in tasks.values() for resource in t.resources}
    for resource, sequence in resource_orders.items():
        intervals = sorted((r['dispatch'], r['finish'], r['task']) for r in rows if resource in r['resources'])
        assert all(a[1] <= b[0] + eps for a, b in zip(intervals, intervals[1:])), 'resource overlap'
        if result['policy'] == 'A' and not result['metrics']['intervention_applied']:
            assert [t for _, _, t in intervals] == sequence, 'fixed resource order violated'
        if result['policy'] == 'H' and resource.endswith(('.mxu', '.vpu')):
            assert [t for _, _, t in intervals] == sequence, 'H compute resource order violated'

    # Address ownership includes output construction at dispatch and live readers
    # through their completion. Pairwise interval replay is separate from DAG reachability.
    for i, old in enumerate(contract.buffers):
        end_old = max([byid[old.owner]['finish']] + [byid[x]['finish'] for x in old.readers])
        for new in contract.buffers[i + 1:]:
            if old.domain != new.domain or max(old.address, new.address) >= min(old.address + old.size, new.address + new.size):
                continue
            end_new = max([byid[new.owner]['finish']] + [byid[x]['finish'] for x in new.readers])
            assert end_old <= byid[new.owner]['dispatch'] + eps or end_new <= byid[old.owner]['dispatch'] + eps, 'physical ownership overlap'

    # Recompute resource-free, admission/legal-ready alternatives over wall time.
    points = sorted({0., result['latency'], *issue_releases,
                     *(r[k] for r in rows for k in ('dispatch', 'finish')),
                     *(a['time'] for a in admission.values()), *deliveries.values()})
    opportunity = 0.
    for start, stop in zip(points, points[1:]):
        if start >= result['latency'] or stop <= start + eps:
            continue
        at = (start + stop) / 2
        issued = {name for name, r in byid.items() if r['dispatch'] < at}
        busy = {resource for r in rows if r['dispatch'] < at < r['finish'] for resource in r['resources']}
        lanes = [0.] * hw['issue_width']
        for r in rows:
            if r['dispatch'] < at:
                lane = min(range(len(lanes)), key=lanes.__getitem__)
                lanes[lane] = r['dispatch'] + hw['issue_cycle']
        if min(lanes) > at:
            continue
        for name, r in byid.items():
            if name in issued or r['ready'] > at or any(resource in busy for resource in tasks[name].resources):
                continue
            needed = tasks[name].resources if result['policy'] == 'A' else tuple(resource for resource in tasks[name].resources if resource.endswith(('.mxu', '.vpu')))
            if result['policy'] == 'B':
                needed = ()
            blocked = any(next((x for x in resource_orders[resource] if x not in issued), None) != name for resource in needed)
            if blocked:
                opportunity += min(stop, result['latency']) - start
                break
    close(opportunity, result['metrics']['opportunity_union_cycles'], 'opportunity wall-time union')
    close(max(r['finish'] for r in rows), result['latency'], 'makespan')
    return {'tasks': len(tasks), 'notifications': len(notices), 'opportunity_union_replayed': opportunity,
            'checks': 'issue/wakeup/admission/calendar/dependency/resource/address/opportunity'}


def check_late_admission() -> dict:
    from dataclasses import replace
    from sim.workload import Task, Edge, Workload
    from sim.compiler import Contract
    from sim.memory import allocate
    from sim.hardware_model import Hardware
    from r4.engine import Prepared, Environment, simulate
    tasks = tuple(Task(n, 'compute', (n,), 1, output_bytes=64) for n in ('a', 'b', 'z'))
    graph = Workload('redteam_late', tasks, (Edge('a', 'z'), Edge('b', 'z')), '')
    contract = Contract(graph, allocate(graph), {n.tid: 0 for n in tasks}, ('a', 'b', 'z'), {})
    hw = Hardware(window=1, completion_latency=10, wakeup_width=1, wakeup_cycle=5)
    checked = []
    for policy in ('A', 'B', 'H'):
        result = simulate(Prepared(contract, hw), Environment(0), policy, detailed=True)
        check_trace(contract, result, contract.admission_order)
        assert abs(result['latency'] - 17.) < 1e-9
        checked.append(policy)
    return {'policies': checked, 'latency': 17., 'scope': 'late admission plus serialized wakeup; full-history reference'}


def check_counterfactual_clock() -> dict:
    from sim.workload import Task, Edge, Workload
    from sim.compiler import Contract
    from sim.memory import allocate
    from sim.hardware_model import Hardware
    from r4.engine import Prepared, Environment, simulate
    graph = Workload('redteam_intervention', (Task('p', 'compute', ('p',), 100),
        Task('h', 'compute', ('r',), 10), Task('b', 'compute', ('r',), 10)), (Edge('p', 'h'),), '')
    contract = Contract(graph, allocate(graph), {'p': 100, 'h': 50, 'b': 0}, ('p', 'h', 'b'), {})
    prepared = Prepared(contract, Hardware(issue_width=1, issue_cycle=5))
    baseline = simulate(prepared, Environment(0), 'A', detailed=True)
    intervention = {'time': baseline['opportunities'][0]['time'], 'task': 'b'}
    changed = simulate(prepared, Environment(0), 'A', detailed=True, intervention=intervention)
    assert intervention['time'] == 5. and baseline['latency'] == 120.
    assert changed['metrics']['intervention_applied'] and changed['latency'] == 110.
    check_trace(contract, changed, contract.admission_order)
    return {'baseline': 120., 'one_action': 110., 'intervention_time': 5., 'event_clock_probe': 'passed'}


def main():
    import json
    from pathlib import Path
    from dataclasses import replace
    from r4.qwen_lowering import build_cases as qwen, build_attention_fused
    from r4.flux_lowering import build_cases as flux, build_optimized_cases
    from r4.fusion import fuse_vpu
    from r4.lowering import Target, lower
    from r4.engine import Prepared, Environment, simulate

    output = {'scope': 'independent abstract-contract and float64 mathematical audit; no silicon or production compiler acceptance',
              'alias_probe': check_alias_two_readers(), 'late_admission_probe': check_late_admission(),
              'counterfactual_clock_probe': check_counterfactual_clock(), 'numeric': [], 'contracts': [], 'traces': []}
    for case in [fuse_vpu(c) for c in qwen() + flux() + [build_attention_fused()] + build_optimized_cases()]:
        output['numeric'].append(check_case_orders(case))
        target = Target()
        contract, info = lower(case, target)
        output['contracts'].append({'case': case.name, **check_tensor_contract(case, contract, info)})
        variants = [('default', target, target.hardware()),
            ('window1_slow_wakeup', target, replace(target.hardware(), window=1, completion_latency=7, wakeup_cycle=5))]
        split = replace(target, sram_ports=4, sram_binding='engine', sram_bytes_cycle_per_port=32)
        variants.append(('split_engine_ports', split, split.hardware()))
        for variant, selected_target, hw in variants:
            contract, info = lower(case, selected_target)
            check_tensor_contract(case, contract, info)
            for seed in (11, 23):
                for mode in ('deterministic', 'service', 'calendar', 'combined'):
                    for policy in ('A', 'B', 'H'):
                        result = simulate(Prepared(contract, hw), Environment(seed, mode), policy, detailed=True)
                        output['traces'].append({'case': case.name, 'hardware_variant': variant, 'seed': seed,
                            'mode': mode, 'policy': policy, **check_trace(contract, result, contract.admission_order)})
    output['source_hashes_at_audit'] = {str(p).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path('r4').glob('*.py'))}
    snapshot = json.loads(Path('r4/r3_snapshot/manifest.json').read_text(encoding='utf8'))
    mismatches = [path for path, digest in snapshot['prior_results'].items() if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest]
    mismatches += [path for path, digest in snapshot['sources'].items() if path.startswith('sim/') and hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest]
    assert not mismatches, f'R3 changed: {mismatches}'
    output['r3_preservation'] = {'original_result_hashes_checked': len(snapshot['prior_results']), 'public_sim_files_checked': sum(p.startswith('sim/') for p in snapshot['sources']), 'status': 'passed'}
    destination = Path('experiments/results/r4/redteam_checks.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'status': 'passed', 'numeric_cases': len(output['numeric']), 'independent_traces': len(output['traces']), 'output': str(destination)}, ensure_ascii=False))


def check_exact_probe():
    """Enumerate permutations and analytically replay zero-cost fixed orders."""
    import itertools
    import json
    from pathlib import Path
    saved = json.loads(Path('experiments/results/r4/exact_probe.json').read_text(encoding='utf8'))
    tasks = {t['tid']: t for t in saved['workload']['tasks']}
    dependencies = {name: set() for name in tasks}
    for e in saved['workload']['edges']:
        dependencies[e['consumer']].add(e['producer'])
    resource_set = sorted({r for t in tasks.values() for r in t['resources']})
    signatures, legal_count = {}, 0
    for order in itertools.permutations(tasks):
        positions = {name: i for i, name in enumerate(order)}
        if any(positions[p] >= positions[name] for name in tasks for p in dependencies[name]):
            continue
        legal_count += 1
        signature = tuple(tuple(name for name in order if r in tasks[name]['resources']) for r in resource_set)
        if signature in signatures:
            continue
        times = []
        for scenario in (0, 1):
            completed, resource_finish = {}, {r: 0. for r in resource_set}
            for name in order:
                task = tasks[name]
                factor = 1.
                if name == 'load.pack.ffn_gu0': factor = (.5, 1.5)[scenario]
                if name == 'load.pack.ffn_gu1': factor = (1.5, .5)[scenario]
                start = max([0.] + [completed[p] for p in dependencies[name]] + [resource_finish[r] for r in task['resources']])
                completed[name] = start + task['predicted'] * factor
                for resource in task['resources']:
                    resource_finish[resource] = completed[name]
            times.append(max(completed.values()))
        signatures[signature] = times
    optimum = min(sum(t) / 2 for t in signatures.values())
    oracle = [min(t[s] for t in signatures.values()) for s in (0, 1)]
    assert legal_count == saved['topological_orders']
    assert len(signatures) == saved['unique_resource_orders']
    assert abs(optimum - saved['optimal_static']['mean']) < 1e-9
    assert oracle == saved['clairvoyant_optimum_each_scenario']
    assert abs(saved['search_exact_gap_pct'] - 100 * (saved['search_mean'] / optimum - 1)) < 1e-9
    return {'independent_topological_orders': legal_count, 'unique_resource_orders': len(signatures),
            'optimal_static_mean': optimum, 'clairvoyant_scenarios': oracle,
            'method': 'permutation enumeration plus earliest-time recurrence, not event simulator'}


def check_summary_statistics():
    import csv
    from pathlib import Path
    directory = Path('experiments/results/r4')
    samples = list(csv.DictReader((directory / 'samples.csv').open(encoding='utf8')))
    summary = list(csv.DictReader((directory / 'summary.csv').open(encoding='utf8')))
    baseline = {(r['config'], r['seed']): float(r['latency']) for r in samples if r['policy'] == 'S'}
    for row in summary:
        selected = [r for r in samples if r['config'] == row['config'] and r['policy'] == row['policy']]
        n = len(selected)
        values = sorted(float(r['latency']) for r in selected)
        reductions = [100 * (baseline[(r['config'], r['seed'])] - float(r['latency'])) / baseline[(r['config'], r['seed'])] for r in selected]
        mean = sum(reductions) / n
        variance = sum((x - mean) ** 2 for x in reductions) / (n - 1) if n > 1 else 0.
        error = 1.96 * math.sqrt(variance / n)
        expected = {'n': n, 'latency_mean': sum(values) / n, 'latency_p95': values[math.ceil(.95 * n) - 1],
                    'paired_reduction_pct': mean, 'ci95_low': mean - error, 'ci95_high': mean + error}
        for key, value in expected.items():
            assert math.isclose(float(row[key]), value, abs_tol=1e-8, rel_tol=1e-8), f'summary mismatch: {row["config"]}:{key}'
    return {'sample_rows': len(samples), 'summary_rows': len(summary), 'mean_p95_paired_ci': 'passed',
            'interval_scope': 'normal sample interval for synthetic paired draws; no multiplicity adjustment or real-hardware uncertainty'}


def audit_saved_artifacts():
    """Independently replay the complete finished sweep from emitted contracts."""
    import csv
    import gzip
    import json
    from pathlib import Path
    from sim.workload import Task, Edge, Workload
    from sim.memory import Buffer
    from sim.compiler import Contract
    from sim.hardware_model import Hardware
    from r4.qwen_lowering import build_cases as qwen, build_attention_fused
    from r4.flux_lowering import build_cases as flux, build_optimized_cases
    from r4.fusion import fuse_vpu

    output_dir = Path('experiments/results/r4')
    manifest = json.loads((output_dir / 'manifest.json').read_text(encoding='utf8'))
    assert manifest['status'] == 'complete', 'main sweep is not frozen/complete'
    for path, expected in manifest['source_hashes'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, f'changed execution source: {path}'
    train, validation, test = map(set, (manifest['training_seeds'], manifest['validation_seeds'], manifest['test_seeds']))
    assert not (train & validation or train & test or validation & test), 'seed split overlap'
    cases = {c.name: c for c in (fuse_vpu(c) for c in qwen() + flux() + [build_attention_fused()] + build_optimized_cases())}
    samples = list(csv.DictReader((output_dir / 'samples.csv').open(encoding='utf8')))
    sample_index = {(r['config'], int(r['seed']), r['policy']): r for r in samples}
    assert len(sample_index) == len(samples), 'duplicate sample'
    seen = set()
    report = {'status': 'passed', 'source_hash_count': len(manifest['source_hashes']), 'configurations': [],
              'numeric_trace_checks': 0, 'trace_count': 0, 'counterfactuals': 0,
              'scope': 'independent replay from all stored contracts/traces; no external device validation'}
    report['independent_exact_probe'] = check_exact_probe()
    report['summary_statistics'] = check_summary_statistics()
    report['checker_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for item in manifest['configurations']:
        config = item['id']
        graph = json.loads((output_dir / 'contracts' / f'{config}.json').read_text(encoding='utf8'))
        search = json.loads((output_dir / 'search' / f'{config}.json').read_text(encoding='utf8'))
        assert set(search['training_seeds']) == train and set(search['validation_seeds']) == validation
        candidates = {tuple(c['order']): c for c in search['candidates']}
        selected = tuple(graph['selected_order'])
        old = tuple(graph['old_order'])
        assert selected == tuple(search['selected_order']) and old == tuple(search['old_pool_order'])
        val_candidates = [c for c in search['candidates'] if c['validation_mean'] is not None]
        winner = min(val_candidates, key=lambda c: (c['validation_mean'], c['training_mean'], tuple(c['order'])))
        assert selected == tuple(winner['order']), 'selected static plan not holdout-validation winner'
        w = graph['workload']
        workload = Workload(w['name'], tuple(Task(**{**t, 'resources': tuple(t['resources'])}) for t in w['tasks']), tuple(Edge(**e) for e in w['edges']), w['description'])
        buffers = tuple(Buffer(**{**b, 'readers': tuple(b['readers'])}) for b in graph['buffers'])
        contract = Contract(workload, buffers, graph['priority'], selected,
            {r: tuple(v) for r, v in graph['resource_order'].items()})
        contract.validate(Hardware(**graph['hardware']))
        case = cases[item['case']]
        check_tensor_contract(case, contract, graph['info'])
        node_names = {n.name for n in case.nodes}
        per_environment = {}
        config_count = 0
        with gzip.open(output_dir / f'{config}.traces.jsonl.gz', 'rt', encoding='utf8') as stream:
            for line in stream:
                result = json.loads(line)
                key = (config, result['seed'], result['label'])
                assert key in sample_index and key not in seen, 'unlisted or duplicate trace'
                seen.add(key)
                assert result['config'] == config and result['seed'] in test
                assert result['environment']['seed'] == result['seed'] and result['environment']['mode'] == item['mode']
                digest = hashlib.sha256(json.dumps(result['environment'], sort_keys=True).encode()).hexdigest()
                assert digest == result['environment_hash'] == sample_index[key]['environment_hash']
                per_environment.setdefault(result['seed'], set()).add(digest)
                expected_policy = {'S8': 'A', 'S': 'A', 'B0': 'B', 'B2': 'B', 'B8': 'B', 'H2': 'H'}[result['label']]
                assert result['policy'] == expected_policy
                expected_extra = {'S8': 0, 'S': 0, 'B0': 0, 'B2': 2, 'B8': 8, 'H2': 2}[result['label']]
                assert result['hardware']['dispatch_latency'] == graph['hardware']['dispatch_latency'] + expected_extra
                for field, value in graph['hardware'].items():
                    if field != 'dispatch_latency':
                        assert result['hardware'][field] == value, f'policy hardware mismatch: {field}'
                check_trace(contract, result, old if result['label'] == 'S8' else selected)
                assert abs(result['latency'] - float(sample_index[key]['latency'])) < 1e-8
                if result['seed'] == 0:
                    order = [r['task'] for r in result['trace'] if r['task'] in node_names]
                    values = case.evaluate(order)
                    for name in case.outputs:
                        np.testing.assert_allclose(values[name], case.reference[name], rtol=1e-5, atol=1e-6)
                    report['numeric_trace_checks'] += 1
                report['trace_count'] += 1
                config_count += 1
        assert all(len(v) == 1 for v in per_environment.values()), 'policies used different exogenous environments'
        assert config_count == len(test) * 6, 'incomplete config trace coverage'
        report['configurations'].append({'config': config, 'traces': config_count,
            'static_candidates': len(candidates), 'search_budget_exhausted': search['budget_exhausted']})
        print(f"artifact audit {len(report['configurations'])}/{len(manifest['configurations'])}: {config}", flush=True)
    assert seen == set(sample_index), 'sample/trace coverage mismatch'
    assert report['trace_count'] == manifest['executions']
    counterfactuals = json.loads((output_dir / 'counterfactual_summary.json').read_text(encoding='utf8'))
    counters = {}
    for expected in counterfactuals:
        config = expected['config']
        index = counters.get(config, 0)
        counters[config] = index + 1
        result = json.loads((output_dir / 'counterfactuals' / f'{config}.{index}.json').read_text(encoding='utf8'))
        graph = json.loads((output_dir / 'contracts' / f'{config}.json').read_text(encoding='utf8'))
        w = graph['workload']
        contract = Contract(Workload(w['name'], tuple(Task(**{**t, 'resources': tuple(t['resources'])}) for t in w['tasks']), tuple(Edge(**e) for e in w['edges']), w['description']),
            tuple(Buffer(**{**b, 'readers': tuple(b['readers'])}) for b in graph['buffers']), graph['priority'], tuple(graph['selected_order']),
            {r: tuple(v) for r, v in graph['resource_order'].items()})
        assert result['intervention'] == expected['action']
        assert result['metrics']['intervention_applied'] == expected['applied']
        assert abs(result['latency'] - expected['counterfactual_latency']) < 1e-8
        check_trace(contract, result, graph['selected_order'])
        report['counterfactuals'] += 1
    assert report['counterfactuals'] == manifest['counterfactuals']
    listed_count = sum(counters.values())
    report['unreferenced_counterfactual_files'] = len(list((output_dir / 'counterfactuals').glob('*.json'))) - listed_count
    assert report['unreferenced_counterfactual_files'] == 0, 'stale counterfactual files from older run'
    report['test_seed_count'] = len(test)
    report['train_seed_count'] = len(train)
    report['validation_seed_count'] = len(validation)
    (output_dir / 'redteam_artifact_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'configurations'}, ensure_ascii=False))


if __name__ == '__main__':
    import sys
    if '--artifacts' in sys.argv:
        audit_saved_artifacts()
    else:
        main()
