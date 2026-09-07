"""Independent full artifact audit for the posthoc compiler-hint probe."""
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from dataclasses import replace

import numpy as np
from sim.workload import Task, Edge, Workload
from sim.memory import Buffer
from sim.compiler import Contract
from r4.redteam_checks import check_trace
from r4.qwen_lowering import build_cases as qwen, build_attention_fused
from r4.flux_lowering import build_cases as flux, build_optimized_cases
from r4.fusion import fuse_vpu


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    main_dir = Path('experiments/results/r4')
    out = main_dir / 'priority_probe'
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf8'))
    assert manifest['status'] == 'complete'
    assert sha(main_dir / 'manifest.json') == manifest['main_manifest_sha256']
    assert sha(main_dir / 'samples.csv') == manifest['baseline_samples_sha256']
    assert sha(Path('r4/priority_probe.py')) == manifest['probe_source_sha256']
    for path, expected in manifest['source_hashes'].items():
        assert sha(Path(path)) == expected
    base = {(r['config'], int(r['seed'])): r for r in csv.DictReader((main_dir / 'samples.csv').open(encoding='utf8')) if r['policy'] == 'S'}
    samples = list(csv.DictReader((out / 'samples.csv').open(encoding='utf8')))
    samples_by_id = {(r['config'], int(r['seed']), r['policy']): r for r in samples}
    assert len(samples_by_id) == len(samples)
    cases = {c.name: c for c in (fuse_vpu(c) for c in qwen() + flux() + [build_attention_fused()] + build_optimized_cases())}
    seen = set()
    count, numeric = 0, 0
    for index, item in enumerate(manifest['configurations']):
        config = item['id']
        assert sha(out / 'plans' / (config + '.json')) == item['priority_plan_sha256']
        source = main_dir / 'contracts' / (config + '.json')
        assert sha(source) == item['source_contract_sha256']
        graph = json.loads(source.read_text(encoding='utf8'))
        plan = json.loads((out / 'plans' / (config + '.json')).read_text(encoding='utf8'))
        w = graph['workload']
        contract = Contract(Workload(w['name'], tuple(Task(**{**t, 'resources': tuple(t['resources'])}) for t in w['tasks']), tuple(Edge(**e) for e in w['edges']), w['description']),
            tuple(Buffer(**{**b, 'readers': tuple(b['readers'])}) for b in graph['buffers']), graph['priority'], tuple(graph['selected_order']),
            {r: tuple(v) for r, v in graph['resource_order'].items()})
        assert plan['selected_order'] == graph['selected_order']
        assert plan['original_priority'] == graph['priority']
        nominal = plan['nominal_static_trace']
        assert nominal['environment']['mode'] == 'deterministic' and nominal['environment']['seed'] == -1
        check_trace(contract, nominal, graph['selected_order'])
        order = [r['task'] for r in nominal['trace']]
        assert order == plan['nominal_static_dispatch_order']
        assert plan['priority'] == {name: len(order) - i for i, name in enumerate(order)}
        hinted = replace(contract, priority=plan['priority'])
        case = cases[w['name']]
        node_names = {n.name for n in case.nodes}
        for line in gzip.open(out / (config + '.traces.jsonl.gz'), 'rt', encoding='utf8'):
            result = json.loads(line)
            key = config, result['seed'], result['label']
            assert key in samples_by_id and key not in seen
            seen.add(key)
            baseline = base[(config, result['seed'])]
            assert result['policy'] == 'B'
            assert result['seed'] in manifest['test_seeds'] and result['environment']['seed'] == result['seed']
            envhash = hashlib.sha256(json.dumps(result['environment'], sort_keys=True).encode()).hexdigest()
            assert envhash == result['environment_hash'] == baseline['environment_hash']
            assert result['baseline_static_latency'] == float(baseline['latency'])
            extra = {'B_order0': 0, 'B_order2': 2}[result['label']]
            for field, value in graph['hardware'].items():
                assert result['hardware'][field] == (value + extra if field == 'dispatch_latency' else value)
            check_trace(hinted, result, graph['selected_order'])
            assert abs(result['latency'] - float(samples_by_id[key]['latency'])) < 1e-8
            if result['seed'] == 0:
                values = case.evaluate([r['task'] for r in result['trace'] if r['task'] in node_names])
                for key in case.outputs:
                    np.testing.assert_allclose(values[key], case.reference[key], rtol=1e-5, atol=1e-6)
                numeric += 1
            count += 1
        if (index + 1) % 10 == 0:
            print(f'priority artifact audit {index + 1}/70', flush=True)
    assert seen == set(samples_by_id) and count == manifest['executions'] == 4480
    summaries = list(csv.DictReader((out / 'summary.csv').open(encoding='utf8')))
    for row in summaries:
        ss = [s for s in samples if s['config'] == row['config'] and s['policy'] == row['policy']]
        times = sorted(float(s['latency']) for s in ss)
        gains = [100 * (float(base[s['config'], int(s['seed'])]['latency']) - float(s['latency'])) / float(base[s['config'], int(s['seed'])]['latency']) for s in ss]
        n = len(gains)
        mean = sum(gains) / n
        half = 1.96 * math.sqrt(sum((x - mean) ** 2 for x in gains) / (n - 1) / n)
        for field, value in {'n': n, 'latency_mean': sum(times) / n, 'latency_p95': times[math.ceil(.95 * n) - 1], 'paired_reduction_pct': mean, 'ci95_low': mean - half, 'ci95_high': mean + half}.items():
            assert math.isclose(float(row[field]), value, abs_tol=1e-8, rel_tol=1e-8)
    report = {'status': 'passed', 'nominal_hint_plans': len(manifest['configurations']), 'trace_count': count,
        'numeric_seed0_checks': numeric, 'summary_rows_checked': len(summaries),
        'checker_sha256': sha(Path(__file__)), 'scope': 'posthoc mathematical/abstract artifact audit; reused test set, no confirmatory or hardware acceptance claim',
        'source_hashes': manifest['source_hashes'], 'probe_sha256': manifest['probe_source_sha256']}
    (out / 'redteam_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print({k: v for k, v in report.items() if k != 'source_hashes'})


if __name__ == '__main__':
    main()
