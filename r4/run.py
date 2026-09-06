"""Reproduce the R4 held-out sweep without model weight downloads."""
from dataclasses import asdict, replace
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import statistics
import time
import numpy as np
from r4.qwen_lowering import build_cases as qwen, build_attention_fused
from r4.flux_lowering import build_cases as flux, build_optimized_cases
from r4.fusion import fuse_vpu
from r4.lowering import lower, Target, fixed_order
from r4.engine import Prepared, Environment, simulate
from r4.static_search import optimize

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/results/r4'


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)), encoding='utf-8')


def source_hashes():
    paths = [ROOT / 'r4' / f for f in ('run.py','engine.py','graph.py','lowering.py','fusion.py','static_search.py','qwen_lowering.py','flux_lowering.py','exact_probe.py')]
    paths += list((ROOT/'sim').rglob('*.py'))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def all_cases():
    ordinary = [fuse_vpu(c) for c in qwen()+flux()]
    optimized = [fuse_vpu(c) for c in [build_attention_fused()]+build_optimized_cases()]
    return ordinary, optimized


def configurations():
    base, optimized = all_cases()
    target = Target()
    rows = []
    for case in base:
        for mode in ('deterministic','service','calendar','combined'):
            rows.append((case, target, mode, 'main'))
        for t in (
            replace(target, name='dma16', dma_bytes_cycle=16),
            replace(target, name='dma64', dma_bytes_cycle=64),
            replace(target, name='sram_one_port', sram_ports=1),
            replace(target, name='one_operand_slot', operand_slots=1),
            replace(target, name='four_operand_slots', operand_slots=4),
            replace(target, name='sram2MiB', memory_capacity=2*1024*1024),
            replace(target, name='sram8MiB', memory_capacity=8*1024*1024)):
            rows.append((case,t,'service','hardware_sensitivity'))
    for case in optimized:
        for mode in ('deterministic','service','calendar','combined'):
            rows.append((case,target,mode,'fusion_conditioning_sensitivity'))
    # Same aggregate SRAM bandwidth (128 B/cycle), four half-bandwidth ports.
    # Unlike the conservative core-port model, MXU may overlap VPU/DMA locally.
    split = replace(target,name='split_engine_ports',sram_ports=4,sram_binding='engine',sram_bytes_cycle_per_port=32)
    for case in base+optimized:
        for mode in ('service','calendar'):
            rows.append((case,split,mode,'pipeline_port_sensitivity'))
    return rows


def numeric_check(case, result):
    ids = {n.name for n in case.nodes}
    order = [x['task'] for x in result['trace'] if x['task'] in ids]
    values = case.evaluate(order)
    errors = {k: float(np.max(np.abs(values[k]-case.reference[k]))) for k in case.outputs}
    if max(errors.values()) > 1e-10:
        raise AssertionError(errors)
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds',type=int,default=32)
    parser.add_argument('--search-budget',type=int,default=128)
    parser.add_argument('--limit',type=int,default=0)
    args = parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    start=time.time()
    configs=configurations()
    if args.limit:
        configs=configs[:args.limit]
    initial_hash=source_hashes()
    manifest={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'python':platform.python_version(),'numpy':np.__version__,'args':vars(args),
        'source_hashes':initial_hash,'training_seeds':list(range(10000,10012)),
        'validation_seeds':list(range(20000,20008)),'test_seeds':list(range(args.seeds)),
        'configurations':[], 'status':'running',
        'scope':'Source-transcribed scaled random-weight graphs, analytical uncalibrated timing. No full model or real hardware performance.'}
    write_json(OUT/'manifest.json',manifest)
    sample_rows, summaries, numerical, interventions = [], [], [], []
    for number,(case,target,mode,group) in enumerate(configs):
        config=f'{case.name}__{target.name}__{mode}'
        contract,info=lower(case,target)
        hw=target.hardware()
        pp=Prepared(contract,hw)
        train=[Environment(s,mode) for s in manifest['training_seeds']]
        validation=[Environment(s,mode) for s in manifest['validation_seeds']]
        selected,old,search=optimize(pp,train,validation,args.search_budget)
        selected_contract=fixed_order(contract,selected,'R4_train_search_validation_selected')
        selected_contract.validate(hw)
        graph={'workload':asdict(contract.workload),'buffers':[asdict(b) for b in contract.buffers],
            'priority':contract.priority,'selected_order':selected,'old_order':old,
            'resource_order':selected_contract.resource_order,'descriptors':selected_contract.descriptors(),
            'hardware':asdict(hw),'info':info}
        write_json(OUT/'contracts'/f'{config}.json',graph)
        write_json(OUT/'search'/f'{config}.json',search)
        stats=[]
        with gzip.open(OUT/f'{config}.traces.jsonl.gz','wt',encoding='utf-8') as stream:
            for seed in manifest['test_seeds']:
                env=Environment(seed,mode)
                env_hash=hashlib.sha256(json.dumps(asdict(env),sort_keys=True).encode()).hexdigest()
                trial={}
                for label,policy,extra,plan in (
                    ('S8','A',0,old),('S','A',0,selected),('B0','B',0,selected),
                    ('B2','B',2,selected),('B8','B',8,selected),('H2','H',2,selected)):
                    result=simulate(pp,env,policy,order=plan,hardware=target.hardware(extra),detailed=True)
                    result.update(config=config,seed=seed,label=label,environment_hash=env_hash)
                    stream.write(json.dumps(result,separators=(',',':'))+'\n')
                    trial[label]=result
                    row={'config':config,'group':group,'case':case.name,'target':target.name,
                        'mode':mode,'seed':seed,'policy':label,'latency':result['latency'],
                        'environment_hash':env_hash,'opportunity_union_cycles':result['metrics']['opportunity_union_cycles'],
                        'ready_order_inversion_rate':result['metrics']['ready_order_inversion_rate']}
                    sample_rows.append(row)
                    if seed==0:
                        numerical.append({'config':config,'policy':label,'max_abs_error':numeric_check(case,result)})
                stats.append({label:r['latency'] for label,r in trial.items()})
                if seed==0:
                    count=0
                    for opportunity in trial['S']['opportunities']:
                        for task in opportunity['alternatives'][:2]:
                            if count>=6:
                                break
                            action={'time':opportunity['time'],'task':task}
                            probe=simulate(pp,env,'A',order=selected,detailed=True,intervention=action)
                            probe.update(config=config,seed=seed,label='offline_one_escape_counterfactual',intervention=action)
                            write_json(OUT/'counterfactuals'/f'{config}.{count}.json',probe)
                            interventions.append({'config':config,'artifact':f'counterfactuals/{config}.{count}.json','action':action,'static_latency':trial['S']['latency'],
                                'counterfactual_latency':probe['latency'],'reduction_cycles':trial['S']['latency']-probe['latency'],
                                'applied':probe['metrics']['intervention_applied']})
                            count+=1
                        if count>=6:
                            break
        for label in ('S8','S','B0','B2','B8','H2'):
            times=[s[label] for s in stats]
            gains=[100*(s['S']-s[label])/s['S'] for s in stats]
            error=1.96*statistics.stdev(gains)/math.sqrt(len(gains)) if len(gains)>1 else 0
            summaries.append({'config':config,'group':group,'case':case.name,'target':target.name,'mode':mode,
                'policy':label,'n':len(times),'latency_mean':statistics.mean(times),
                'latency_p95':sorted(times)[math.ceil(.95*len(times))-1],
                'paired_reduction_pct':statistics.mean(gains),
                'ci95_low':statistics.mean(gains)-error,'ci95_high':statistics.mean(gains)+error,
                'tasks':len(contract.workload.tasks),'sram_high_water_bytes':info['sram_high_water_bytes'],
                'search_unique':len(search['candidates']),'search_budget_exhausted':search['budget_exhausted']})
        manifest['configurations'].append({'id':config,'group':group,'target':asdict(target),'mode':mode,
            'case':case.name,'tasks':len(contract.workload.tasks),'source_builder_seed':7,
            'source_numeric_seed':8 if 'linear_decode' in case.name or 'single_scaled' in case.name else 7})
        print(f'[{number+1}/{len(configs)}] {config}: B2 {summaries[-3]["paired_reduction_pct"]:+.3f}%',flush=True)
        write_json(OUT/'manifest.json',manifest)
    for filename,rows in (('samples.csv',sample_rows),('summary.csv',summaries)):
        with (OUT/filename).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(OUT/'numeric_schedule_checks.json',numerical)
    write_json(OUT/'counterfactual_summary.json',interventions)
    if source_hashes()!=initial_hash:
        raise AssertionError('Execution source changed during sweep; rerun required')
    manifest.update(status='complete',elapsed_seconds=time.time()-start,executions=len(sample_rows),
                    numeric_schedule_checks=len(numerical),counterfactuals=len(interventions))
    manifest['active_counterfactual_artifacts'] = [r['artifact'] for r in interventions]
    write_json(OUT/'manifest.json',manifest)
    print(f'Complete: {len(sample_rows)} executions in {time.time()-start:.1f}s',flush=True)


if __name__=='__main__':
    main()
