"""Frozen R5 comparisons. python -X utf8 -B -m r5.run_experiments"""
from dataclasses import asdict, replace
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import gzip
import hashlib
import json
import statistics
import time
import numpy as np
from r5.model import Hardware, Plan, build
from r5.resource_sim import Environment, simulate
from r5.static_plans import candidates, neighbors
from r5.replay_audit import audit

ROOT=Path(__file__).resolve().parent
TRAIN=(1000,1001)
VALID=(1100,1101)
TEST=tuple(range(2000,2012))
WORKLOADS=('qwen_projection','flux_projection','qwen_gdn_state')
RUNTIME=('model.py','resource_sim.py','coarse_sim.py','static_plans.py','run_experiments.py','replay_audit.py')


def configurations():
    base=Hardware()
    configs=[(f'ref_{mode}',base,mode) for mode in ('none','latency','bank_background','bus_background','combined')]
    configs += [(f'o{n}_combined',replace(base,outstanding=n),'combined') for n in (1,4,32)]
    configs += [(f'r{n}_combined',replace(base,return_slots=n),'combined') for n in (1,2)]
    configs += [('fifo_combined',replace(base,bank_arbitration='fifo'),'combined'),
                ('banks1_combined',replace(base,banks=1),'combined')]
    return configs


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def confidence(values):
    a=np.array(values,dtype=float)
    rng=np.random.default_rng(9417)
    boots=a[rng.integers(0,len(a),(4096,len(a)))].mean(axis=1)
    return [float(x) for x in np.quantile(boots,[.025,.975])]


def one_case(args):
    workload,label,hw,mode,backend,outdir=args
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    if backend=='atomic':
        from r5.coarse_sim import coarse_simulate
        engine=coarse_simulate
    else:engine=simulate
    case=f'{backend}__{workload}__{label}'
    plans=candidates(workload,hw)
    graphs={p.bank_color:build(workload,p.bank_color,hw) for p in plans}
    def run(p,seed,policy='S',extra=0,detailed=False):
        return engine(graphs[p.bank_color],hw,p,Environment(seed,mode),policy,extra,detailed)
    training=[]
    for p in plans:
        times=[run(p,s)['latency'] for s in TRAIN]
        training.append({'plan':asdict(p),'train':times,'train_mean':statistics.mean(times)})
    training.sort(key=lambda x:(x['train_mean'],x['plan']['name']))
    initial_plan_count=len(plans)
    seen={(p.order,p.bank_color,p.dma_spacing) for p in plans}
    byname={p.name:p for p in plans};local_count=0
    while local_count<64:
        best=byname[training[0]['plan']['name']]
        batch=[]
        for order in neighbors(graphs[best.bank_color],best):
            signature=(order,best.bank_color,best.dma_spacing)
            if signature in seen:continue
            seen.add(signature)
            p=Plan(order,best.bank_color,best.dma_spacing,f'local{local_count+len(batch):03}')
            batch.append(p)
            if len(batch)>=min(16,64-local_count):break
        if not batch:break
        for p in batch:
            times=[run(p,s)['latency'] for s in TRAIN]
            training.append({'plan':asdict(p),'train':times,'train_mean':statistics.mean(times)})
            plans.append(p);byname[p.name]=p
        local_count+=len(batch)
        training.sort(key=lambda x:(x['train_mean'],x['plan']['name']))
    shortlist=[]
    for entry in training[:3]:
        p=byname[entry['plan']['name']]
        times=[run(p,s)['latency'] for s in VALID]
        shortlist.append({'plan':asdict(p),'validation':times,'validation_mean':statistics.mean(times)})
    shortlist.sort(key=lambda x:(x['validation_mean'],x['plan']['name']))
    selected=byname[shortlist[0]['plan']['name']]
    graph=graphs[selected.bank_color]
    rows=[];trace_files=[]
    for seed in TEST:
        latencies={};results={}
        for tag,policy,extra in (('S','S',0),('B0','B',0),('B2','B',2)):
            detailed=backend=='request' or seed==TEST[0]
            r=run(selected,seed,policy,extra,detailed)
            replay=audit(graph,r) if backend=='request' else None
            r['environment_hash']=digest(r['environment'])
            latencies[tag]=r['latency']
            results[tag]={'latency':r['latency'],'metrics':r['metrics'],'environment_hash':r['environment_hash'],'independent_replay':replay}
            if seed==TEST[0]:
                if backend=='request':
                    raw=sorted((x['task'],x['index'],x['address'],x['bytes'],x.get('external_latency',0)) for x in r['requests'])
                    r['logical_requests_hash']=digest(raw)
                r['graph']=asdict(graph)
                path=outdir/f'{case}__{seed}__{tag}.json.gz'
                with gzip.open(path,'wt',encoding='utf8',compresslevel=3) as f:json.dump(r,f,separators=(',',':'))
                trace_files.append(path.name)
        s=latencies['S']
        total_ext=sum(sp.size for c in graph.commands if c.kind=='dma' for sp in c.spans)
        external_lb=Environment(seed,mode).finish(0,total_ext/hw.external_bw,'external')
        compute_lb=max((sum(c.cycles for c in graph.commands if c.engine==e and c.kind=='compute') for e in {c.engine for c in graph.commands}),default=0)
        mem_lb=sum(sp.size for c in graph.commands for sp in c.spans)/hw.sram_bw
        bound=max(external_lb,compute_lb,mem_lb)
        assert s>=bound-1e-6,(case,s,bound)
        rows.append({'seed':seed,'results':results,'B0_gain_pct':100*(1-latencies['B0']/s),
            'B2_gain_pct':100*(1-latencies['B2']/s),'resource_lower_bound':bound,
            'loose_max_gain_pct':100*(1-bound/s)})
    summary={'case':case,'backend':backend,'workload':workload,'configuration':label,'mode':mode,
        'hardware':asdict(hw),'metadata':graph.metadata,'plan_count':len(plans),
        'initial_plan_count':initial_plan_count,'local_plan_count':local_count,
        'selected_plan':asdict(selected),'training':training,'validation':shortlist,
        'train_seeds':TRAIN,'validation_seeds':VALID,'test_seeds':TEST,'rows':rows,'trace_files':trace_files,
        'mean_latency':{tag:statistics.mean(x['results'][tag]['latency'] for x in rows) for tag in ('S','B0','B2')},
        'mean_gain_pct':{tag:statistics.mean(x[f'{tag}_gain_pct'] for x in rows) for tag in ('B0','B2')},
        'gain_ci95_pct':{tag:confidence([x[f'{tag}_gain_pct'] for x in rows]) for tag in ('B0','B2')},
        'mean_loose_max_gain_pct':statistics.mean(x['loose_max_gain_pct'] for x in rows),
        'execution_count':len(plans)*len(TRAIN)+3*len(VALID)+len(TEST)*3}
    path=outdir/f'{case}.json'
    path.write_text(json.dumps(summary,indent=2),encoding='utf8')
    return {k:summary[k] for k in ('case','mean_latency','mean_gain_pct','gain_ci95_pct','execution_count','plan_count')}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=3)
    ap.add_argument('--backend',choices=('request','atomic','all'),default='all')
    ap.add_argument('--only',default='');ap.add_argument('--output',default=str(ROOT/'results'))
    args=ap.parse_args()
    tasks=[]
    for workload in WORKLOADS:
        for label,hw,mode in configurations():
            if args.backend in ('request','all'):tasks.append((workload,label,hw,mode,'request',args.output))
            if label in ('ref_none','ref_combined') and args.backend in ('atomic','all'):
                tasks.append((workload,label,hw,mode,'atomic',args.output))
    if args.only:tasks=[x for x in tasks if args.only in '__'.join((x[4],x[0],x[1]))]
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    manifest={'runtime_sha256':{f'here/{x}':hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in RUNTIME if (ROOT/x).exists()},
        'plan_sha256':hashlib.sha256((ROOT/'experiment_plan.md').read_bytes()).hexdigest(),
        'train':TRAIN,'validation':VALID,'test':TEST,'task_count':len(tasks),
        'numeric_settings':'hypothetical structural sensitivity; not target NPU calibration',
        'output':args.output,'invocation_backend':args.backend,'only':args.only}
    (out/'run_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    start=time.perf_counter();summaries=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(one_case,t) for t in tasks]
        for f in as_completed(futures):
            s=f.result();summaries.append(s)
            print(json.dumps({'done':len(summaries),'total':len(tasks),**s},ensure_ascii=False),flush=True)
    (out/'summary.json').write_text(json.dumps({'cases':sorted(summaries,key=lambda x:x['case']),
        'wall_seconds':time.perf_counter()-start,'execution_count':sum(x['execution_count'] for x in summaries)},indent=2),encoding='utf8')


if __name__=='__main__':main()
