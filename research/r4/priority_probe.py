"""Post-hoc compiler-priority-only corrective probe; frozen R4 runtime.

Construct every hint from selected TRAIN/VALIDATION plans and a nominal,
deterministic static replay before reading any held-out latency for scoring.
This is exploratory use of the existing test set, not a confirmatory experiment.
"""
from dataclasses import asdict, replace
from pathlib import Path
import csv, gzip, hashlib, json, math, statistics, time
from r4.run import configurations, numeric_check, source_hashes, write_json
from r4.lowering import lower
from r4.engine import Prepared, Environment, simulate

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'experiments/results/r4'
OUT=MAIN/'priority_probe'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(obj):return json.loads(json.dumps(obj))


def main():
    start=time.time();OUT.mkdir(parents=True,exist_ok=True)
    original_manifest=json.loads((MAIN/'manifest.json').read_text())
    runtime_hash=source_hashes()
    assert original_manifest['status']=='complete'
    assert runtime_hash==original_manifest['source_hashes'],'Main runtime must remain frozen'
    test_seeds=original_manifest['test_seeds']
    configs=configurations()
    assert len(configs)==len(original_manifest['configurations'])==70
    manifest={'status':'constructing_priorities','scope':'Post-hoc compiler-priority-only corrective probe, not new hardware and not an independent confirmatory test',
              'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              'source_hashes':runtime_hash,'probe_source_sha256':digest(Path(__file__)),
              'main_manifest_sha256':digest(MAIN/'manifest.json'),
              'hint_environment':asdict(Environment(-1,'deterministic')),
              'hint_rule':'priority[task] = task_count - position in nominal S dispatch trace; no held-out service/latency enters construction',
              'test_seeds':test_seeds,'policies':['B_order0','B_order2'],
              'unchanged':['task graph and service demands','mapping','addresses and buffers','admission order passed to runtime','static resource order passed to runtime','issue/wakeup/control model'],
              'configurations':[]}
    write_json(OUT/'manifest.json',manifest)
    plans=[]
    # Stage 1 is completed for all cases before the scoring table is opened.
    for case,target,mode,group in configs:
        config=f'{case.name}__{target.name}__{mode}'
        path=MAIN/'contracts'/f'{config}.json'
        saved=json.loads(path.read_text())
        contract,info=lower(case,target)
        assert normalized(asdict(contract.workload))==saved['workload'],config
        assert normalized([asdict(b) for b in contract.buffers])==saved['buffers'],config
        assert normalized(contract.priority)==saved['priority'],config
        selected=tuple(saved['selected_order'])
        nominal=simulate(Prepared(contract,target.hardware()),Environment(-1,'deterministic'),
                         'A',order=selected,hardware=target.hardware(),detailed=True)
        dispatch_order=[entry['task'] for entry in nominal['trace']]
        assert len(dispatch_order)==len(set(dispatch_order))==len(contract.workload.tasks)
        priority={tid:len(dispatch_order)-position for position,tid in enumerate(dispatch_order)}
        hinted=replace(contract,priority=priority)
        assert replace(hinted,priority=contract.priority)==contract,'Priority must be sole contract change'
        prepared=Prepared(hinted,target.hardware())
        plan={'config':config,'source_contract_sha256':digest(path),'selected_order':selected,
              'nominal_static_dispatch_order':dispatch_order,'priority':priority,
              'original_priority':contract.priority,'nominal_environment':asdict(Environment(-1,'deterministic')),
              'nominal_static_trace':nominal,'priority_only_contract_change_checked':True}
        write_json(OUT/'plans'/f'{config}.json',plan)
        plans.append((case,target,mode,group,config,selected,prepared))
        manifest['configurations'].append({'id':config,'source_contract_sha256':digest(path),
            'priority_plan_sha256':digest(OUT/'plans'/f'{config}.json'),'tasks':len(dispatch_order)})
    manifest['priority_construction_completed_before_test_table_open']=True
    manifest['status']='running';write_json(OUT/'manifest.json',manifest)
    # Held-out outcomes enter only comparison, after all hints are immutable.
    with (MAIN/'samples.csv').open(newline='',encoding='utf-8') as f:
        baseline={(r['config'],int(r['seed'])):r for r in csv.DictReader(f) if r['policy']=='S'}
    assert len(baseline)==70*len(test_seeds)
    manifest['baseline_samples_sha256']=digest(MAIN/'samples.csv')
    samples=[];summaries=[];numeric=[];threshold=[]
    for number,(case,target,mode,group,config,selected,prepared) in enumerate(plans):
        results={'B_order0':[],'B_order2':[]}
        with gzip.open(OUT/f'{config}.traces.jsonl.gz','wt',encoding='utf-8') as stream:
            for seed in test_seeds:
                env=Environment(seed,mode)
                envhash=hashlib.sha256(json.dumps(asdict(env),sort_keys=True).encode()).hexdigest()
                static=baseline[config,seed]
                assert envhash==static['environment_hash'],'Common random sample mismatch'
                static_latency=float(static['latency'])
                for label,extra in (('B_order0',0),('B_order2',2)):
                    result=simulate(prepared,env,'B',order=selected,hardware=target.hardware(extra),detailed=True)
                    result.update(config=config,seed=seed,label=label,environment_hash=envhash,
                        priority_plan=f'plans/{config}.json',baseline_static_latency=static_latency,
                        scope='post-hoc compiler-priority-only corrective probe')
                    stream.write(json.dumps(result,separators=(',',':'))+'\n')
                    gain=100*(static_latency-result['latency'])/static_latency
                    row={'config':config,'group':group,'case':case.name,'target':target.name,'mode':mode,
                         'seed':seed,'policy':label,'latency':result['latency'],'static_latency':static_latency,
                         'paired_reduction_pct':gain,'environment_hash':envhash}
                    samples.append(row);results[label].append(row)
                    if seed==0:numeric.append({'config':config,'policy':label,'max_abs_error':numeric_check(case,result)})
        for label,rows in results.items():
            gains=[r['paired_reduction_pct'] for r in rows];times=[r['latency'] for r in rows]
            mean=statistics.mean(gains);half=1.96*statistics.stdev(gains)/math.sqrt(len(gains))
            summaries.append({'config':config,'group':group,'case':case.name,'target':target.name,'mode':mode,
                'policy':label,'n':len(rows),'latency_mean':statistics.mean(times),
                'latency_p95':sorted(times)[math.ceil(.95*len(times))-1],
                'paired_reduction_pct':mean,'ci95_low':mean-half,'ci95_high':mean+half})
            if label=='B_order2' and mean>=5:
                threshold.append(summaries[-1]);print('EXPLORATORY_THRESHOLD_ALERT',json.dumps(summaries[-1]),flush=True)
        if (number+1)%10==0:print(f'priority probe {number+1}/70; last B_order2 {summaries[-1]["paired_reduction_pct"]:+.3f}%',flush=True)
    for name,rows in (('samples.csv',samples),('summary.csv',summaries)):
        with (OUT/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(OUT/'numeric_schedule_checks.json',numeric)
    write_json(OUT/'threshold_alerts.json',threshold)
    assert source_hashes()==runtime_hash,'Frozen runtime changed during corrective probe'
    assert digest(Path(__file__))==manifest['probe_source_sha256'],'Probe source changed during run'
    assert digest(MAIN/'manifest.json')==manifest['main_manifest_sha256'],'Main manifest changed'
    assert digest(MAIN/'samples.csv')==manifest['baseline_samples_sha256'],'Baseline samples changed'
    for entry in manifest['configurations']:
        assert digest(OUT/'plans'/f'{entry["id"]}.json')==entry['priority_plan_sha256'],'Frozen hint changed'
    decisions={}
    for label in ('B_order0','B_order2'):
        rows=[r for r in summaries if r['policy']==label]
        decisions[label]={'positive':sum(r['paired_reduction_pct']>1e-9 for r in rows),
                         'negative':sum(r['paired_reduction_pct']<-1e-9 for r in rows),
                         'zero':sum(abs(r['paired_reduction_pct'])<=1e-9 for r in rows),
                         'best':max(rows,key=lambda r:r['paired_reduction_pct']),
                         'worst':min(rows,key=lambda r:r['paired_reduction_pct'])}
    write_json(OUT/'decision_summary.json',decisions)
    manifest.update(status='complete',executions=len(samples),numeric_schedule_checks=len(numeric),
        no_testfuture_leak_checks='All hints constructed before reading baseline table; only nominal deterministic S trace supplies rank; same task/address/mapping/selected order; shared test environment hashes checked',
        threshold_alerts=len(threshold),elapsed_seconds=time.time()-start)
    write_json(OUT/'manifest.json',manifest)
    print(json.dumps({'executions':len(samples),'elapsed_seconds':manifest['elapsed_seconds'],'decisions':decisions},indent=2),flush=True)


if __name__=='__main__':main()
