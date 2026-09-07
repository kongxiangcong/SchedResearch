"""Run qualification first; independent compiler splits, then frozen test pairs."""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import statistics
from .model import ROOT, C, plans, build, metrics, qualifications, digest
from .simulator import run


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.gz':
        with gzip.open(path, 'wt', encoding='utf-8', compresslevel=3) as f:
            json.dump(obj, f, separators=(',', ':'))
    else:
        path.write_text(json.dumps(obj, indent=2), encoding='utf-8')


def verify_registration():
    for name in ('preregistration_manifest.json', 'implementation_semantics_manifest.json'):
        manifest = json.loads((ROOT / name).read_text())
        for p, expected in manifest['files'].items():
            assert hashlib.sha256((ROOT.parent / p).read_bytes()).hexdigest() == expected, p


def summarize(values):
    mean = statistics.mean(values)
    half = C['gate']['t_critical_df29'] * statistics.stdev(values) / len(values) ** .5
    return dict(n=len(values), mean_gain_pct=mean, ci95_pct=[mean - half, mean + half],
                minimum_gain_pct=min(values), maximum_gain_pct=max(values))


def main():
    verify_registration()
    q = qualifications()
    write(ROOT / 'qualification_results.json', q)
    print('Qualification PASS: full 32-head prefill state traffic differs; decode canonical graphs identical.', flush=True)
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write(ROOT / 'execution_started.json', dict(started_utc=start, contract_sha256=digest(C)))
    selected, selections = {}, {}
    for variant in ('baseline', 'resident'):
        ranking = []
        for p in plans(variant):
            g = build(p)
            records = [dict(seed=s, condition=c, elapsed=run(g, s, c)['elapsed'])
                       for s in range(110100, 110108) for c in ('quiet', 'background')]
            ranking.append(dict(plan=p, train=records, train_mean=statistics.mean(x['elapsed'] for x in records)))
        ranking.sort(key=lambda x: (x['train_mean'], x['plan']['name']))
        validation = []
        for rec in ranking[:3]:
            g = build(rec['plan'])
            records = [dict(seed=s, condition=c, elapsed=run(g, s, c)['elapsed'])
                       for s in range(110200, 110208) for c in ('quiet', 'background')]
            validation.append(dict(plan=rec['plan'], validation=records,
                                   mean=statistics.mean(x['elapsed'] for x in records)))
        validation.sort(key=lambda x: (x['mean'], x['plan']['name']))
        selected[variant] = validation[0]['plan']
        selections[variant] = dict(train_ranking=ranking, validation=validation, selected=selected[variant])
        print('Selected', selected[variant], flush=True)
    write(ROOT / 'selection.json', dict(frozen_before_test_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                        variants=selections, selected=selected))
    graphs, graph_files = {}, {}
    for variant, p in selected.items():
        g = graphs[variant] = build(p)
        name = graph_files[variant] = f'results/{variant}_graph.json.gz'
        write(ROOT / name, g)
    rows = []
    for group, seeds, condition in [('quiet', [111000], 'quiet'),
                                     ('A', range(111000, 111030), 'background'),
                                     ('B', range(112000, 112030), 'background')]:
        for s in seeds:
            pair = {}
            for variant in ('baseline', 'resident'):
                result = run(graphs[variant], s, condition, True)
                result['graph_file'] = graph_files[variant]
                name = f'results/{group}_{s}_{variant}.json.gz'
                write(ROOT / name, result)
                pair[variant] = dict(elapsed=result['elapsed'], trace=name,
                                     lower_bounds=result['lower_bounds'])
            rows.append(dict(group=group, seed=s, results=pair,
                             gain_pct=100 * (1 - pair['resident']['elapsed'] / pair['baseline']['elapsed'])))
        print('Finished held-out', group, flush=True)
    quiet = rows[0]
    stats = {group: summarize([r['gain_pct'] for r in rows if r['group'] == group]) for group in ('A', 'B')}
    passed = quiet['gain_pct'] >= 5 and all(s['mean_gain_pct'] >= 5 and s['ci95_pct'][0] > 0 for s in stats.values())
    outcome = dict(status='PERFORMANCE_COMPLETE_PENDING_INDEPENDENT_AUDIT',
                   started_utc=start, selected=selected, quiet=quiet, statistics=stats, rows=rows,
                   metrics={v: metrics(g) for v, g in graphs.items()},
                   capacity={v: g['metadata'] for v, g in graphs.items()},
                   prefill_performance_gate=passed,
                   decode='EXCLUDED_NO_INTERVENTION_UNDER_REGISTERED_ABI',
                   provisional_investment_decision='成立，可以继续探索' if passed else '本轮未获支持，方向关闭',
                   limitations=['Uncalibrated reference; cold weights and staged ABI only.',
                                'Timing is command-level execution; independent numerical tensors are not executed per timing trace.',
                                'No all-hardware or all-residency impossibility, no full decoder/model throughput.'])
    write(ROOT / 'results.json', outcome)
    print(json.dumps(dict(quiet_gain_pct=quiet['gain_pct'], statistics=stats,
                          prefill_performance_gate=passed), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
