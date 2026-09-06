"""R10 stage A. Refuses existing output; no changes to frozen artifacts."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import argparse, itertools, json, gzip, hashlib, random, statistics, time
from concurrent.futures import ProcessPoolExecutor
from r10.model import build_graph, simulate
from r10.bounds import lower_bounds
from r9.run_experiment import pool as old_pool, cid, stats

def save(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def phases(seed,n):
    r=random.Random(seed)
    return [r.random()*8192 for _ in range(n)]
CONDS={'quiet':0.,'reserved20':.2,'reserved35':.35}
def env(c,p): return dict(period=8192.,duty=CONDS[c],phase=p)
def pool():
    records={r['id']:r for r in old_pool()}
    for m,k,mc,bp,rx,layout,order,q in itertools.product(('C2N','C2K'),(256,512,1024),(False,True),((1,1),(2,1),(2,2)),(False,True),('gather','row'),('xw','wx'),(1,2,4)):
        c=dict(mapping=m,ktile=k,multicast=mc,buffers=bp[0],prefetch=bp[1],resident_x=rx,layout=layout,order=order,outstanding=q,reverse=False)
        records[cid(c)]={'id':cid(c),'config':c}
    return sorted(records.values(),key=lambda x:x['id'])
def evaluate_job(job):
    rec,hw,ps=job
    try:g=build_graph(hw,rec['config'])
    except (ValueError,AssertionError) as e:return rec|dict(legal=False,reason=str(e))
    values={c:[simulate(g,hw,env(c,p))['elapsed'] for p in ([0.] if c=='quiet' else ps)] for c in CONDS}
    return rec|dict(legal=True,elapsed=values)
def evaluate(records,hw,ps,workers,label):
    result=[]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i,r in enumerate(ex.map(evaluate_job,[(r,hw,ps) for r in records],chunksize=2),1):
            result.append(r)
            if i%50==0: print(label,i,'/',len(records),flush=True)
    return result
def score(r,c):return statistics.mean(r['elapsed'][c]),r['id']
def shortlist(tr):
    ids=set()
    for m,mc,c in itertools.product(('C2N','C2K','C1N'),(False,True),CONDS):
        g=[r for r in tr if r['legal'] and r['config']['mapping']==m and r['config']['multicast']==mc]
        ids.update(r['id'] for r in sorted(g,key=lambda r:score(r,c))[:4])
    return ids
def trace(out,name,hw,e,c,g,r):
    p=out/'traces'/(name+'.json.gz')
    with gzip.open(p,'wt',encoding='utf8',compresslevel=3) as f:
        json.dump(dict(hardware=hw,environment=e,config=c,graph=g,result=r),f,separators=(',',':'))
    return dict(path=str(p.relative_to(out)),sha256=sha(p))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='r10/results');ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    out=ROOT/a.output;out.mkdir();(out/'traces').mkdir();started=time.time()
    hw0=json.loads((ROOT/'r10/reference_hardware.json').read_text())
    variants={'EXT128':hw0|{'external_bytes_per_cycle':128},'DMA32':hw0|{'cluster_dma_bytes_per_cycle':32}}
    ps={k:phases(seed,n) for k,seed,n in [('train',1010000,8),('validation',1020000,8),('test_s1',1030000,30),('test_s2',1040000,30)]}
    candidates=pool();catalog={r['id']:r['config'] for r in candidates}
    save(out/'registration.json',dict(candidates=candidates,phases=ps,hardware=variants,plan_sha256=sha(ROOT/'r10/experiment_plan.md'),model_sha256=sha(ROOT/'r10/model.py'),runner_sha256=sha(Path(__file__))))
    old=json.loads((ROOT/'r9/results/sensitivity.json').read_text())
    rows=[];traces=[];selections={};summaries={}
    for label,hw in variants.items():
        tr=evaluate(candidates,hw,ps['train'],a.workers,label+' train');save(out/(label+'_training.json'),tr)
        ids=shortlist(tr);vr=evaluate([r for r in candidates if r['id'] in ids],hw,ps['validation'],a.workers,label+' validation');save(out/(label+'_validation.json'),vr)
        chosen={c:min([r for r in vr if r['legal'] and r['config']['mapping']!='C1N'],key=lambda r:score(r,c))['id'] for c in CONDS}
        controls={c:min([r for r in vr if r['legal'] and r['config']['mapping']=='C1N'],key=lambda r:score(r,c))['id'] for c in CONDS}
        prior=next(x for x in old if (x['field'],x['value'])==(('external_bytes_per_cycle',128) if label=='EXT128' else ('cluster_dma_bytes_per_cycle',32)))
        priorcat={r['id']:r['config'] for r in prior['training']}
        selections[label]=dict(selected=chosen,control=controls,old_selected=prior['selected']);save(out/'selection.json',selections)
        for session,c in itertools.product((1,2),CONDS):
            for block,p in enumerate(ps[f'test_s{session}']):
                e=env(c,p); conf=catalog[chosen[c]];g=build_graph(hw,conf);r=simulate(g,hw,e,detailed=True);lb=lower_bounds(g,hw,e)
                oc=priorcat[prior['selected'][c]];og=build_graph(hw,oc);orr=simulate(og,hw,e,detailed=block==0);olb=lower_bounds(og,hw,e)
                assert lb['tight']<=r['elapsed']+1e-6 and olb['tight']<=orr['elapsed']+1e-6
                name=f'{label}.s{session}.{c}.b{block}'
                tf=trace(out,name,hw,e,conf,g,r);traces.append(tf)
                row=dict(hardware=label,session=session,condition=c,block=block,phase=p,selected_id=chosen[c],elapsed=r['elapsed'],old_elapsed=orr['elapsed'],bounds=lb,old_bounds=olb,trace=tf['path'])
                if block==0:
                    t=trace(out,name+'.old',hw,e,oc,og,orr);traces.append(t);row['old_trace']=t['path']
                    cc=catalog[controls[c]];cg=build_graph(hw,cc);cr=simulate(cg,hw,e,detailed=True)
                    t=trace(out,name+'.C1N',hw,e,cc,cg,cr);traces.append(t);row['control_trace']=t['path'];row['control_elapsed']=cr['elapsed']
                rows.append(row)
            group=[x for x in rows if (x['hardware'],x['session'],x['condition'])==(label,session,c)]
            summaries[f'{label}.s{session}.{c}']={
                'static_gain_pct':stats([100*(1-x['elapsed']/x['old_elapsed']) for x in group]),
                'old_aggregate_upper_pct':stats([100*(1-x['old_bounds']['aggregate']/x['old_elapsed']) for x in group]),
                'old_tight_upper_pct':stats([100*(1-x['old_bounds']['tight']/x['old_elapsed']) for x in group]),
                'new_aggregate_upper_pct':stats([100*(1-x['bounds']['aggregate']/x['elapsed']) for x in group]),
                'new_tight_upper_pct':stats([100*(1-x['bounds']['tight']/x['elapsed']) for x in group])}
            save(out/'test_pairs.json',rows);save(out/'summary.json',summaries);save(out/'trace_manifest.json',traces)
            print(label,session,c,summaries[f'{label}.s{session}.{c}'],flush=True)
    save(out/'completion.json',dict(status='COMPLETE',pairs=len(rows),traces=len(traces),seconds=time.time()-started,registration_sha256=sha(out/'registration.json'),selection_sha256=sha(out/'selection.json')))
if __name__=='__main__':main()
