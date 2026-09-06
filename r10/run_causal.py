"""Fixed-rule independent Stage B sessions, no tuning or hindsight selection."""
import sys,json,itertools,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from r10.run_experiment import save,sha,phases,env,CONDS,trace
from r10.causal_model import simulate,build_graph
from r9.run_experiment import stats

def main():
    a=ROOT/'r10/results';assert (a/'completion.json').exists()
    out=ROOT/'r10/causal_results';out.mkdir();(out/'traces').mkdir()
    ar=json.loads((a/'registration.json').read_text());selection=json.loads((a/'selection.json').read_text());catalog={r['id']:r['config'] for r in ar['candidates']}
    ps={k:phases(seed,n) for k,seed,n in [('train',1110000,8),('validation',1120000,8),('test_s1',1130000,30),('test_s2',1140000,30)]}
    save(out/'registration.json',dict(phases=ps,hardware=ar['hardware'],selection=selection,stage_a_selection_sha256=sha(a/'selection.json'),plan_sha256=sha(ROOT/'r10/causal_plan.md'),model_sha256=sha(ROOT/'r10/causal_model.py'),runner_sha256=sha(Path(__file__))))
    diagnostics=[];rows=[];traces=[];summary={};started=time.time()
    for label,h in ar['hardware'].items():
        for c in CONDS:
            conf=catalog[selection[label]['selected'][c]];g=build_graph(h,conf)
            for split in ('train','validation','test_s1','test_s2'):
                test=split.startswith('test')
                for block,p in enumerate(ps[split]):
                    e=env(c,p);base=simulate(g,h,e,detailed=test);action=simulate(g,h,e,detailed=test,causal=True)
                    row=dict(hardware=label,condition=c,split=split,block=block,phase=p,static_id=selection[label]['selected'][c],baseline=base['elapsed'],causal=action['elapsed'],gain_pct=100*(1-action['elapsed']/base['elapsed']),action_applied=action['intervention_applied'])
                    if test:
                        for role,r in [('baseline',base),('causal',action)]:
                            tf=trace(out,f'{label}.{c}.{split}.{block}.{role}',h,e,conf,g,r);traces.append(tf);row[role+'_trace']=tf['path']
                        row['total_charge']=sum(d['cost_cycles'] for d in action['ext_decisions']);rows.append(row)
                    else:diagnostics.append(row)
                if test:
                    group=[r for r in rows if (r['hardware'],r['condition'],r['split'])==(label,c,split)]
                    summary[f'{label}.{split}.{c}']=stats([r['gain_pct'] for r in group])
                    print(label,split,c,summary[f'{label}.{split}.{c}'],flush=True)
                save(out/'diagnostics.json',diagnostics);save(out/'test_pairs.json',rows);save(out/'summary.json',summary);save(out/'trace_manifest.json',traces)
    gates={label:all(summary[f'{label}.test_s{s}.{c}']['mean']>=5 and summary[f'{label}.test_s{s}.{c}']['ci95_t'][0]>0 for s,c in itertools.product((1,2),('reserved20','reserved35'))) and all(summary[f'{label}.test_s{s}.quiet']['min']>=-1 for s in (1,2)) for label in ar['hardware']}
    save(out/'completion.json',dict(status='COMPLETE',pairs=len(rows),traces=len(traces),diagnostics=len(diagnostics),gate=gates,seconds=time.time()-started))
if __name__=='__main__':main()
