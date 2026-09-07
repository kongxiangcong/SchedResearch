"""Independent necessary-condition and evidence audit. No simulator/runner imports."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import json, math, random, statistics, itertools, hashlib
from r9.independent_check import audit_trace, read_json, digest, require, same, available_cycles

def finish(start,work,e):
    lo=start;hi=start+work/(1-e['duty'])+2*e['period']
    for _ in range(70):
        mid=(lo+hi)/2
        if available_cycles(start,mid,e)<work:lo=mid
        else:hi=mid
    return lo

def bound(g,h,e):
    er=h['external_bytes_per_cycle'];dr=h['cluster_dma_bytes_per_cycle']
    latency=h['request_latency_cycles'];visibility=h['visibility_cycles']
    nodes={n['id']:n for n in g['nodes']}
    q=min(g['config']['outstanding'],h['dma_outstanding_per_cluster'],h['transport_slots_per_cluster'])
    ext=0;locals=[0.]*h['clusters'];cores=[0.]*(h['clusters']*2);occup=[0.]*h['clusters'];read_sizes=[[] for _ in locals]
    for n in nodes.values():
        if 'packets' not in n:cores[n['core']]+=n['duration'];continue
        for p in n['packets']:
            c=n['cluster'];ext+=p['external_bytes'];locals[c]+=p['local_bytes']/dr
            occup[c]+=latency+visibility+p['external_bytes']/er+p['local_bytes']/dr
            if n['kind']=='dma_read':read_sizes[c].append(p['local_bytes']/dr)
    # Construct the forbidden local-service tails explicitly; consume ideal
    # local work through the complement, instead of solving runner's capacity.
    starvation=[]
    for sizes in read_sizes:
        work=sum(sizes);buffer=sum(sorted(sizes,reverse=True)[:q]);t=0.
        period=e['period'];phase=e['phase'];length=period*e['duty']
        first=math.floor((-phase-length)/period)
        if length<=buffer:starvation.append(work);continue
        for i in range(first,first+100000):
            start=max(0.,phase+i*period)+buffer;end=phase+i*period+length
            if end<=start or end<=t:continue
            if work<=max(0,start-t):t+=work;work=0;break
            work-=max(0,start-t);t=end
        require(work==0,'blackout integration termination');starvation.append(t)
    memo={}
    def earliest(nid):
        if nid in memo:return memo[nid]
        n=nodes[nid];t=max([earliest(d) for d in n['deps']]+[0.])
        if 'packets' not in n:value=t+n['duration']
        else:
            ep=[p['external_bytes']/er for p in n['packets']];lp=[p['local_bytes']/dr for p in n['packets']];t+=latency
            if n['kind']=='dma_read':
                individual=[finish(t,x,e)+y for x,y in zip(ep,lp)]
                value=max(individual+[finish(t,sum(ep),e),finish(t,min(ep),e)+sum(lp)])+visibility
            else:
                individual=[finish(t+y,x,e) for x,y in zip(ep,lp)]
                value=max(individual+[finish(t+min(lp),sum(ep),e),t+sum(lp)])+visibility
        memo[nid]=value;return value
    parts=dict(aggregate=max([finish(0,ext/er,e)]+locals+cores),credit=max(occup)/q,blackout=max(starvation),dependency=max(earliest(x) for x in g['output_nodes']))
    return parts|{'tight':max(parts.values())}

def verify_bounds(envelope,claimed=None):
    b=bound(envelope['graph'],envelope['hardware'],envelope['environment'])
    require(b['tight']<=envelope['result']['elapsed']+1e-5,'lower bound exceeds actual elapsed')
    if claimed:
        require(all(same(b[k],claimed[k]) for k in b),'independent bound mismatch')
    return b

def main():
    out=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'r10/results')
    reg=read_json(out/'registration.json');sel=read_json(out/'selection.json');rows=read_json(out/'test_pairs.json');summary=read_json(out/'summary.json')
    require(digest(ROOT/'r10/model.py')==digest(ROOT/'r9/model.py')==reg['model_sha256'],'base model identity')
    require(digest(ROOT/'r10/run_experiment.py')==reg['runner_sha256'],'runner identity')
    require(digest(ROOT/'r10/experiment_plan.md')==reg['plan_sha256'],'plan identity')
    for name,seed,n in [('train',1010000,8),('validation',1020000,8),('test_s1',1030000,30),('test_s2',1040000,30)]:
        rng=random.Random(seed);require(reg['phases'][name]==[rng.random()*8192 for _ in range(n)],'phase stream')
    allps=sum(reg['phases'].values(),[]);require(len(set(allps))==76,'phase reuse')
    catalog={x['id']:x['config'] for x in reg['candidates']}
    expected_catalog={r['id']:r['config'] for r in read_json(ROOT/'r9/results/training.json')}
    for mapping,ktile,multicast,bp,resident,layout,order,outstanding in itertools.product(('C2N','C2K'),(256,512,1024),(False,True),((1,1),(2,1),(2,2)),(False,True),('gather','row'),('xw','wx'),(1,2,4)):
        config=dict(mapping=mapping,ktile=ktile,multicast=multicast,buffers=bp[0],prefetch=bp[1],resident_x=resident,layout=layout,order=order,outstanding=outstanding,reverse=False)
        ident=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:12];expected_catalog[ident]=config
    require(catalog==expected_catalog and len(catalog)==960,'independent Cartesian registration')
    for label in reg['hardware']:
        tr=read_json(out/(label+'_training.json'));vr=read_json(out/(label+'_validation.json'))
        require(len(tr)==len(catalog) and {r['id'] for r in tr}==set(catalog),'training coverage')
        ids=set()
        for m in ('C2N','C2K','C1N'):
            for mc in (False,True):
                for c in ('quiet','reserved20','reserved35'):
                    group=[r for r in tr if r['legal'] and r['config']['mapping']==m and r['config']['multicast']==mc]
                    ids.update(r['id'] for r in sorted(group,key=lambda r:(statistics.mean(r['elapsed'][c]),r['id']))[:4])
        require(len(vr)==len(ids) and {r['id'] for r in vr}==ids,'shortlist selection')
        for r in tr+vr:
            require(r['config']==catalog[r['id']],'registered configuration')
            if r['legal']:require([len(r['elapsed'][c]) for c in ('quiet','reserved20','reserved35')]==[1,8,8],'train/val counts')
        for c in ('quiet','reserved20','reserved35'):
            for scope,local in [('selected',False),('control',True)]:
                group=[r for r in vr if r['legal'] and (r['config']['mapping']=='C1N')==local]
                require(sel[label][scope][c]==min(group,key=lambda r:(statistics.mean(r['elapsed'][c]),r['id']))['id'],'validation selection')
    require(len(rows)==360 and len({(r['hardware'],r['session'],r['condition'],r['block']) for r in rows})==360,'paired coverage')
    bytrace={r['trace']:r for r in rows};oldtrace={r['old_trace']:r for r in rows if 'old_trace' in r}
    reports=[];old_graphs={}
    for i,tf in enumerate(read_json(out/'trace_manifest.json'),1):
        p=out/tf['path'];require(digest(p)==tf['sha256'],'trace digest');en=read_json(p)
        report=audit_trace(en);bb=verify_bounds(en)
        r=bytrace.get(tf['path'])
        if r:
            require(en['hardware']==reg['hardware'][r['hardware']],'hardware mutation')
            require(en['config']==catalog[sel[r['hardware']]['selected'][r['condition']]],'selected trace config')
            require(en['environment']==dict(period=8192.,duty={'quiet':0.,'reserved20':.2,'reserved35':.35}[r['condition']],phase=reg['phases'][f"test_s{r['session']}"][r['block']]),'trace phase')
            verify_bounds(en,r['bounds']);require(same(report['elapsed'],r['elapsed']),'elapsed link')
        if tf['path'] in oldtrace:
            r=oldtrace[tf['path']];verify_bounds(en,r['old_bounds']);require(same(report['elapsed'],r['old_elapsed']),'old elapsed link')
            old_graphs[(r['hardware'],r['condition'])]=en['graph']
        reports.append(dict(path=tf['path'],**report,new_bounds=bb))
        if i%40==0:print('audit',i,flush=True)
    for r in rows:
        require(r['phase']==reg['phases'][f"test_s{r['session']}"][r['block']],'numeric row phase')
        e=dict(period=8192.,duty={'quiet':0.,'reserved20':.2,'reserved35':.35}[r['condition']],phase=r['phase'])
        ob=bound(old_graphs[(r['hardware'],r['condition'])],reg['hardware'][r['hardware']],e)
        require(all(same(ob[k],r['old_bounds'][k]) for k in ob),'all old-static bound recomputation')
    funcs={'static_gain_pct':lambda r:100*(1-r['elapsed']/r['old_elapsed']),
           'old_aggregate_upper_pct':lambda r:100*(1-r['old_bounds']['aggregate']/r['old_elapsed']),
           'old_tight_upper_pct':lambda r:100*(1-r['old_bounds']['tight']/r['old_elapsed']),
           'new_aggregate_upper_pct':lambda r:100*(1-r['bounds']['aggregate']/r['elapsed']),
           'new_tight_upper_pct':lambda r:100*(1-r['bounds']['tight']/r['elapsed'])}
    for key,metrics in summary.items():
        h,s,c=key.split('.');group=[r for r in rows if r['hardware']==h and r['session']==int(s[1:]) and r['condition']==c];require(len(group)==30,'group n')
        for k,f in funcs.items():
            v=[f(r) for r in group];mu=math.fsum(v)/30;margin=2.045229642132703*math.sqrt(math.fsum((x-mu)**2 for x in v)/29/30)
            expected=[mu,min(v),max(v),mu-margin,mu+margin];actual=[metrics[k]['mean'],metrics[k]['min'],metrics[k]['max'],*metrics[k]['ci95_t']]
            require(all(same(x,y) for x,y in zip(expected,actual)),'paired statistics')
    completion=read_json(out/'completion.json');require(completion['pairs']==360 and completion['traces']==len(reports),'completion counts')
    cert=dict(status='PASS',traces=len(reports),requests=sum(r['requests'] for r in reports),operations=sum(r['operations'] for r in reports),pairs=360,checker_sha256=digest(Path(__file__)),reports=reports)
    (out/'audit_results.json').write_text(json.dumps(cert,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in cert.items() if k!='reports'}))
if __name__=='__main__':main()
