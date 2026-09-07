"""Posthoc static-gap diagnostic for the two small positive B0 rows.

Configuration selection is posthoc. Candidate construction and selection use
only training/validation environments, not held-out future service times.
"""
import gzip
import hashlib
import json
from pathlib import Path
import statistics
from dataclasses import replace

from r4.qwen_lowering import build_full, build_attention_fused
from r4.fusion import fuse_vpu
from r4.lowering import Target, lower
from r4.engine import Prepared, Environment, simulate


def main():
    directory = Path('experiments/results/r4')
    results = []
    target = replace(Target(), name='split_engine_ports', sram_ports=4,
        sram_binding='engine', sram_bytes_cycle_per_port=32)
    for original in (build_full(), build_attention_fused()):
        case = fuse_vpu(original)
        config = case.name + '__split_engine_ports__service'
        graph = json.loads((directory / 'contracts' / (config + '.json')).read_text(encoding='utf8'))
        c, _ = lower(case, target)
        p = Prepared(c, target.hardware())
        incumbent = tuple(graph['selected_order'])
        options = {incumbent: ['main_static_incumbent']}
        for seed in range(10000, 10012):
            trial = simulate(p, Environment(seed, 'service'), 'B', order=incumbent, detailed=True)
            order = tuple(r['task'] for r in trial['trace'])
            options.setdefault(order, []).append(f'B0_train_trace_{seed}')
        scores = []
        for order, origins in options.items():
            training = statistics.mean(simulate(p, Environment(seed, 'service'), 'A', order=order)['latency'] for seed in range(10000, 10012))
            validation = statistics.mean(simulate(p, Environment(seed, 'service'), 'A', order=order)['latency'] for seed in range(20000, 20008))
            scores.append({'order': order, 'origins': origins, 'training_mean': training, 'validation_mean': validation})
        best = min(scores, key=lambda x: (x['validation_mean'], x['training_mean'], x['order']))
        saved = {}
        for line in gzip.open(directory / (config + '.traces.jsonl.gz'), 'rt', encoding='utf8'):
            r = json.loads(line)
            if r['label'] in ('S', 'B0'):
                saved.setdefault(r['seed'], {})[r['label']] = r['latency']
        samples = []
        for seed in range(32):
            static = simulate(p, Environment(seed, 'service'), 'A', order=best['order'])['latency']
            old = saved[seed]
            samples.append({'seed': seed, 'main_S': old['S'], 'main_B0': old['B0'], 'training_trace_static': static,
                'B0_reduction_vs_new_static_pct': 100 * (static - old['B0']) / static,
                'new_static_reduction_vs_main_S_pct': 100 * (old['S'] - static) / old['S']})
        results.append({'config': config, 'candidate_count': len(scores), 'selected': best, 'all_candidates': scores,
            'B0_reduction_vs_new_static_pct': statistics.mean(r['B0_reduction_vs_new_static_pct'] for r in samples),
            'new_static_reduction_vs_main_S_pct': statistics.mean(r['new_static_reduction_vs_main_S_pct'] for r in samples),
            'samples': samples})
    payload = {'scope': 'posthoc configuration-selected baseline adequacy diagnostic; unchanged task graph/mapping/address/cost; all candidate order generation and selection use train/validation only',
        'train_seeds': list(range(10000, 10012)), 'validation_seeds': list(range(20000, 20008)), 'test_seeds': list(range(32)),
        'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'results': results}
    (directory / 'redteam_static_probe.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf8')
    for r in results:
        print({k: r[k] for k in ('config', 'candidate_count', 'B0_reduction_vs_new_static_pct', 'new_static_reduction_vs_main_S_pct')})


if __name__ == '__main__':
    main()
