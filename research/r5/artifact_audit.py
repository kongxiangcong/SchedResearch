"""Post-run independent artifact/statistics/atomic audit; frozen engine checker stays separate."""
from __future__ import annotations
from collections import defaultdict
import hashlib
from r5.replay_audit import audit, close, occupancy, disjoint, calendar_available


def audit_coarse(graph,result):
    """Independently check the explicitly different command-atomic contrast."""
    cmds={c.cid:c for c in graph.commands}
    rows=result['commands'];byid={r['task']:r for r in rows}
    assert len(rows)==len(cmds) and set(byid)==set(cmds)
    hw,env,metrics=result['hardware'],result['environment'],result['metrics']
    expected_bytes={k:0 for k in ('dma','read','write')}
    intervals=defaultdict(list);engine_intervals=defaultdict(list)
    for cid,c in cmds.items():
        t=byid[cid]
        close(t['start'],t['dispatch']+hw['dispatch']+result['extra_dispatch'],'coarse dispatch')
        close(t['visible'],t['finish']+hw['notification'],'coarse notification')
        assert (t['engine'],t['kind'],t['core'])==(c.engine,c.kind,c.core)
        assert all(t['dispatch']>=byid[d]['visible']-1e-7 for d in c.deps)
        engine_intervals[c.engine].append((t['dispatch'],t['finish']))
        if c.kind=='compute':
            close(t['finish']-t['start'],c.cycles,'coarse compute')
            continue
        size=sum(s.size for s in c.spans);expected_bytes[c.kind]+=size
        if c.kind=='dma':
            factor=1.
            if env['mode'] in ('latency','combined'):
                digest=hashlib.blake2b(f"{env['seed']}:{cid}:0".encode(),digest_size=8).digest()
                factor+=env['latency_amplitude']*(2*int.from_bytes(digest,'big')/(2**64-1)-1)
            assert t['external_start']>=t['start']+hw['external_latency']*factor-1e-7
            work=size/hw['external_bw']
            service=calendar_available(t['external_start'],t['external_end'],env) if env['mode'] in ('bus_background','combined') else t['external_end']-t['external_start']
            close(service,work,'coarse external integral')
            assert t['fabric_start']>=t['external_end']-1e-7
            close(t['fabric_end']-t['fabric_start'],hw['fabric_latency']+size/hw['fabric_bw'],'coarse fabric')
            assert t['sram_start']>=t['fabric_end']-1e-7
            for resource in ('external','fabric'):intervals[resource].append((t[resource+'_start'],t[resource+'_end']))
        else:
            assert t['sram_start']>=t['start']-1e-7
        elapsed=t['sram_end']-t['sram_start']
        if env['mode'] in ('bank_background','combined'):
            available=calendar_available(t['sram_start'],t['sram_end'],env)
            service=elapsed-(elapsed-available)/hw['banks']
        else:service=elapsed
        close(service,size/hw['sram_bw'],'coarse pooled SRAM service integral')
        close(t['finish'],t['sram_end'],'coarse memory completion')
        intervals['sram'].append((t['sram_start'],t['sram_end']))
    for resource,interval in intervals.items():
        disjoint(interval,'coarse '+resource)
        close(metrics[resource+'_service_cycles'],sum(b-a for a,b in interval),'coarse occupancy '+resource)
    for engine,interval in engine_intervals.items():
        kind=next(c.kind for c in graph.commands if c.engine==engine)
        occupancy(interval,hw['dma_commands'] if kind=='dma' else 1,'coarse engine '+engine)
    ordered=sorted(rows,key=lambda r:r['sequence'])
    for a,b in zip(ordered,ordered[1:]):assert b['dispatch']>=a['dispatch']+hw['issue_cycle']-1e-7
    if result['policy']=='S':
        for engine in engine_intervals:
            assert [r['task'] for r in ordered if r['engine']==engine]==[cid for cid in result['plan']['order'] if cmds[cid].engine==engine]
    assert metrics['external_bytes']==metrics['fabric_bytes']==expected_bytes['dma']
    assert metrics['local_read_bytes']==expected_bytes['read']
    assert metrics['local_write_bytes']==expected_bytes['write']
    assert metrics['issue_count']==len(cmds)
    assert metrics['notification_count']==sum(len(c.deps) for c in graph.commands)
    close(result['latency'],max(r['visible'] for r in rows),'coarse latency')
    return {'status':'PASS','commands':len(cmds),'requests':0,'scope':'independent command-atomic stage replay; intentionally lacks finite request queues'}


def from_graph_json(data):
    from r5.model import Graph,Command,Span
    rows=[]
    for row in data['commands']:
        row=dict(row);row['deps']=tuple(row['deps']);row['spans']=tuple(Span(**s) for s in row['spans'])
        rows.append(Command(**row))
    return Graph(data['name'],tuple(rows),data['metadata'])


def audit_artifacts(directory):
    import gzip
    import json
    from pathlib import Path
    import statistics
    import numpy as np
    directory=Path(directory)
    manifest=json.loads((directory/'run_manifest.json').read_text(encoding='utf8'))
    root=Path(__file__).resolve().parent
    for name,digest in manifest['runtime_sha256'].items():
        assert hashlib.sha256((root/name.removeprefix('here/')).read_bytes()).hexdigest()==digest, ('source drift',name)
    assert hashlib.sha256((root/'experiment_plan.md').read_bytes()).hexdigest()==manifest['plan_sha256']
    assert not (set(manifest['train'])&set(manifest['validation']) or set(manifest['train'])&set(manifest['test']) or set(manifest['validation'])&set(manifest['test']))
    cases=[];traces=[];summary_rows=0;seed_rows=0;request_receipts=0;request_receipt_events=0
    for path in sorted(directory.glob('*.json')):
        data=json.loads(path.read_text(encoding='utf8'))
        if 'case' not in data or 'training' not in data:continue
        training=data['training'];validation=data['validation'];rows=data['rows']
        assert len(training)==data['plan_count']
        for row in training:close(row['train_mean'],statistics.mean(row['train']),'training mean')
        train_sorted=sorted(training,key=lambda row:(row['train_mean'],row['plan']['name']))
        assert set(r['plan']['name'] for r in validation)==set(r['plan']['name'] for r in train_sorted[:3]), 'validation shortlist changed'
        for row in validation:close(row['validation_mean'],statistics.mean(row['validation']),'validation mean')
        val_sorted=sorted(validation,key=lambda row:(row['validation_mean'],row['plan']['name']))
        assert data['selected_plan']==val_sorted[0]['plan'],'selection violated validation contract'
        assert data['train_seeds']==manifest['train'] and data['validation_seeds']==manifest['validation'] and data['test_seeds']==manifest['test']
        assert [r['seed'] for r in rows]==manifest['test']
        for row in rows:
            hashes={p['environment_hash'] for p in row['results'].values()};assert len(hashes)==1
            if data['backend']=='request':
                for p in row['results'].values():
                    receipt=p['independent_replay']
                    assert receipt['status']=='PASS'
                    assert receipt['requests']==p['metrics']['request_count']
                    assert receipt['commands']==p['metrics']['issue_count']
                    assert receipt['external_bytes']==p['metrics']['external_bytes']
                    request_receipts+=1;request_receipt_events+=receipt['requests']
            static=row['results']['S']['latency']
            for policy in ('B0','B2'):
                close(row[policy+'_gain_pct'],100*(1-row['results'][policy]['latency']/static),'paired reduction')
            close(row['loose_max_gain_pct'],100*(1-row['resource_lower_bound']/static),'resource-bound gap')
        for policy in ('S','B0','B2'):
            close(data['mean_latency'][policy],statistics.mean(r['results'][policy]['latency'] for r in rows),'summary latency')
        for policy in ('B0','B2'):
            samples=np.asarray([r[policy+'_gain_pct'] for r in rows])
            close(data['mean_gain_pct'][policy],float(samples.mean()),'summary gain')
            rng=np.random.default_rng(9417)
            boot=samples[rng.integers(0,len(samples),(4096,len(samples)))].mean(axis=1)
            expected_ci=np.quantile(boot,[.025,.975])
            for actual,expected in zip(data['gain_ci95_pct'][policy],expected_ci):close(actual,float(expected),'bootstrap interval')
        saved_requests={}
        for filename in data['trace_files']:
            with gzip.open(directory/filename,'rt',encoding='utf8') as handle:record=json.load(handle)
            graph=from_graph_json(record['graph'])
            checked=audit(graph,record) if data['backend']=='request' else audit_coarse(graph,record)
            assert record['plan']==data['selected_plan']
            policy='S' if record['policy']=='S' else ('B2' if record['extra_dispatch']==2 else 'B0')
            seed=record['environment']['seed'];row=next(r for r in rows if r['seed']==seed)
            close(record['latency'],row['results'][policy]['latency'],'saved trace/sample latency')
            assert record['metrics']==row['results'][policy]['metrics']
            digest=lambda obj:hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            assert record['environment_hash']==digest(record['environment'])==row['results'][policy]['environment_hash']
            if data['backend']=='request':
                raw=sorted((r['task'],r['index'],r['address'],r['bytes'],r.get('external_latency',0)) for r in record['requests'])
                assert record['logical_requests_hash']==digest(raw)
                saved_requests.setdefault(seed,set()).add(record['logical_requests_hash'])
            traces.append({'file':filename,**checked})
        assert all(len(hashes)==1 for hashes in saved_requests.values()), 'policy raw request environment differs'
        cases.append(data['case']);summary_rows+=3;seed_rows+=len(rows)*3
    assert len(cases)==manifest['task_count'], ('missing cases',len(cases),manifest['task_count'])
    result={'status':'PASS','cases':len(cases),'summary_policy_rows':summary_rows,'test_policy_rows_recomputed':seed_rows,
            'saved_traces_replayed':len(traces),'request_events_replayed':sum(t['requests'] for t in traces),
            'in_run_request_test_replay_receipts_checked':request_receipts,
            'request_events_in_run_receipts':request_receipt_events,
            'traces':traces,'source_and_preregistration_hashes':'PASS',
            'scope':'all saved detailed traces, every saved statistic/selection; detailed traces may be a subset of test seeds; no device calibration'}
    return result


if __name__=='__main__':
    import argparse
    import json
    from pathlib import Path
    parser=argparse.ArgumentParser();parser.add_argument('--results',required=True);parser.add_argument('--output')
    args=parser.parse_args();result=audit_artifacts(args.results)
    output=Path(args.output) if args.output else Path(args.results)/'independent_replay_audit.json'
    output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='traces'},indent=2))
