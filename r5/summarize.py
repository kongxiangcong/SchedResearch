"""Recompute scientific summary from frozen per-case results; no simulations."""
from pathlib import Path
import json
import statistics


ROOT=Path(__file__).resolve().parent


def main():
    cases=[]
    for path in (ROOT/'results').glob('*.json'):
        data=json.loads(path.read_text(encoding='utf8'))
        if 'case' in data and 'training' in data:cases.append(data)
    assert len(cases)==42,len(cases)
    cases.sort(key=lambda x:x['case'])
    fine=[x for x in cases if x['backend']=='request']
    lookup={(x['backend'],x['workload'],x['configuration']):x for x in cases}
    counts={}
    for tag in ('B0','B2'):
        counts[tag]={
            'positive':sum(x['mean_gain_pct'][tag]>1e-9 for x in fine),
            'zero':sum(abs(x['mean_gain_pct'][tag])<=1e-9 for x in fine),
            'negative':sum(x['mean_gain_pct'][tag]<-1e-9 for x in fine),
            'mean5pct_ci_positive':sum(x['mean_gain_pct'][tag]>=5 and x['gain_ci95_pct'][tag][0]>0 for x in fine),
            'best':max(({'case':x['case'],'gain':x['mean_gain_pct'][tag],'ci95':x['gain_ci95_pct'][tag]} for x in fine),key=lambda x:x['gain'])}
    contrasts=[]
    for w in ('qwen_projection','flux_projection','qwen_gdn_state'):
        quiet=lookup['request',w,'ref_none']
        noisy=lookup['request',w,'ref_combined']
        row={'workload':w,'quiet_cycles':quiet['mean_latency']['S'],'combined_cycles':noisy['mean_latency']['S'],
            'retrained_combined_penalty_pct':100*(noisy['mean_latency']['S']/quiet['mean_latency']['S']-1),
            'quiet_loose_max_gain_pct':quiet['mean_loose_max_gain_pct'],
            'combined_loose_max_gain_pct':noisy['mean_loose_max_gain_pct'],
            'combined_B0_gain_pct':noisy['mean_gain_pct']['B0'],'combined_B2_gain_pct':noisy['mean_gain_pct']['B2'],
            'quiet_external_occupancy':statistics.mean(r['results']['S']['metrics']['external_bus_occupancy'] for r in quiet['rows']),
            'quiet_external_payload_bw':statistics.mean(r['results']['S']['metrics']['external_payload_bw'] for r in quiet['rows']),
            'quiet_compute_utilization':quiet['rows'][0]['results']['S']['metrics']['compute_busy']}
        row['stress_vs_combined_static_multiplier']={c:lookup['request',w,c]['mean_latency']['S']/noisy['mean_latency']['S'] for c in ('o1_combined','o4_combined','r1_combined','r2_combined','fifo_combined','banks1_combined')}
        row['atomic_vs_request']={c:{'atomic':lookup['atomic',w,c]['mean_latency']['S'],
            'request':lookup['request',w,c]['mean_latency']['S'],
            'atomic_B0_gain_pct':lookup['atomic',w,c]['mean_gain_pct']['B0'],
            'request_B0_gain_pct':lookup['request',w,c]['mean_gain_pct']['B0']} for c in ('ref_none','ref_combined')}
        contrasts.append(row)
    all_replay=[r['results'][p]['independent_replay'] for x in fine for r in x['rows'] for p in ('S','B0','B2')]
    assert len(all_replay)==1296 and all(x['status']=='PASS' for x in all_replay)
    stats={'status':'PASS','case_count':len(cases),'request_case_count':len(fine),
        'performance_executions':sum(x['execution_count'] for x in cases),'test_executions':len(cases)*36,
        'request_test_executions_independently_replayed_in_memory':len(all_replay),
        'request_events_checked_in_memory':sum(x['requests'] for x in all_replay),
        'verdict_counts_request':counts,'contrasts':contrasts,
        'scientific_boundary':'Conditional uncalibrated full-width source slices; trained static candidate class, not production compiler or full-model evidence.',
        'GDN_caveat':'Main per-token SRAM roundtrips are not mandated by capacity; see fresh-seed RF-resident compiler control before interpreting GDN.'}
    (ROOT/'results'/'interpretation.json').write_text(json.dumps(stats,indent=2),encoding='utf8')
    lines=['# R5 all frozen cases','',
        'Gains are paired-seed mean percentage latency reductions; positive means faster. Intervals are paired-seed bootstrap95%. All hardware timing is hypothetical. GDN main lowering has an RF-residency baseline limitation.','',
        '| Backend | Workload | Configuration | S cycles | B0 gain% [CI] | B2 gain% [CI] | Static plans |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for x in cases:
        def val(tag):
            a,b=x['gain_ci95_pct'][tag]
            return f"{x['mean_gain_pct'][tag]:+.4f} [{a:+.4f},{b:+.4f}]"
        lines.append(f"| {x['backend']} | {x['workload']} | {x['configuration']} | {x['mean_latency']['S']:.3f} | {val('B0')} | {val('B2')} | {x['plan_count']} |")
    (ROOT/'results'/'all_cases.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(stats,indent=2))


if __name__=='__main__':main()
