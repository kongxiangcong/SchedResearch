"""Independent saved-artifact audit of the posthoc RF residency control."""
from pathlib import Path
from dataclasses import asdict
import gzip
import hashlib
import json
import statistics
import numpy as np
from r5.artifact_audit import from_graph_json
from r5.replay_audit import audit,close


def main():
    root=Path(__file__).resolve().parent
    directory=root/'resident_control_results'
    result=json.loads((root/'resident_control_results.json').read_text(encoding='utf8'))
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf8'))
    assert result['manifest']==manifest
    for name,digest in manifest['frozen_runtime_sha256'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
    assert hashlib.sha256((root/'resident_control.py').read_bytes()).hexdigest()==manifest['control_source_sha256']
    main_manifest=json.loads((root/'results/run_manifest.json').read_text(encoding='utf8'))
    sets=[set(manifest[k]) for k in ('train_seeds','validation_seeds','test_seeds')]
    for i,a in enumerate(sets):
        for b in sets[i+1:]:assert not a&b
        assert not a&set(main_manifest['train']+main_manifest['validation']+main_manifest['test'])
    checked=[];pairs={};total_checked=0
    for config in manifest['configs']:
        label=config['label'];pair={}
        for variant in ('original','resident'):
            row=json.loads((directory/f'{label}__{variant}.json').read_text(encoding='utf8'))
            training=row['training'];validation=row['validation']
            for entry in training+validation:close(entry['mean'],statistics.mean(entry['latencies']),'control mean')
            candidates=sorted(training,key=lambda r:(r['mean'],r['plan']['name']))
            assert {r['plan']['name'] for r in validation}=={r['plan']['name'] for r in candidates[:3]}
            chosen=min(validation,key=lambda r:(r['mean'],r['plan']['name']))
            assert row['selected_plan']==chosen['plan']
            assert [r['seed'] for r in row['rows']]==manifest['test_seeds']
            assert row['all_executions_independently_audited']==len(training)*len(manifest['train_seeds'])+len(validation)*len(manifest['validation_seeds'])+len(manifest['test_seeds'])*3
            total_checked+=row['all_executions_independently_audited']
            for policy in ('S','B0','B2'):
                close(row['mean_latency'][policy],statistics.mean(r['results'][policy]['latency'] for r in row['rows']),'control latency')
            graph=None
            for file in row['trace_files']:
                with gzip.open(directory/file,'rt',encoding='utf8') as handle:trace=json.load(handle)
                graph=from_graph_json(trace['graph']);check=audit(graph,trace)
                assert trace['plan']==row['selected_plan']
                checked.append({'file':file,**check})
                policy='S' if trace['policy']=='S' else ('B2' if trace['extra_dispatch']==2 else 'B0')
                saved=next(r for r in row['rows'] if r['seed']==trace['environment']['seed'])
                close(trace['latency'],saved['results'][policy]['latency'],'control trace latency')
                assert trace['metrics']==saved['results'][policy]['metrics']
                assert trace['independent_audit']==check
            assert graph is not None
            pair[variant]=(row,graph)
        original,old=pair['original'];resident,new=pair['resident']
        # Independent structural check: arithmetic commands cannot change, and
        # per-head state updates must remain in the same token order.
        old_arithmetic={c.cid:c for c in old.commands if c.kind=='compute'}
        new_arithmetic={c.cid:c for c in new.commands if c.kind=='compute'}
        assert set(old_arithmetic)==set(new_arithmetic)
        for cid,c in old_arithmetic.items():
            a,b=asdict(c),asdict(new_arithmetic[cid]);a.pop('deps');b.pop('deps');assert a==b
            token=int(cid.rsplit('.',1)[1])
            assert new_arithmetic[cid].deps==((f'delta{c.core}.{token-1}',) if token else (f'state_read{c.core}.0',))
        assert sum(c.ops for c in old.commands)==sum(c.ops for c in new.commands)==917504
        assert old.metadata['rf_bytes_per_core']==new.metadata['rf_bytes_per_core']==73760
        for graph,expected in ((old,1048576),(new,262144)):
            assert sum(s.size for c in graph.commands if c.kind in ('read','write') for s in c.spans)==expected
            assert sum(s.size for c in graph.commands if c.kind=='dma' for s in c.spans)==131072
        source=next(c for c in result['cases'] if c['configuration']==label)
        effects={key:[] for key in source['effects']}
        for a,b in zip(original['rows'],resident['rows']):
            assert a['seed']==b['seed'];aa,bb=a['results'],b['results']
            os,ns=aa['S']['latency'],bb['S']['latency']
            effects['static_compiler_residency_gain_pct'].append(100*(1-ns/os))
            effects['resident_B0_vs_resident_S_gain_pct'].append(100*(1-bb['B0']['latency']/ns))
            effects['resident_B2_vs_resident_S_gain_pct'].append(100*(1-bb['B2']['latency']/ns))
            effects['original_B0_vs_original_S_gain_pct'].append(100*(1-aa['B0']['latency']/os))
        for name,values in effects.items():
            declared=source['effects'][name]
            for a,b in zip(values,declared['paired_seed_values_pct']):close(a,b,'control paired value')
            close(statistics.mean(values),declared['mean_pct'],'control effect')
            rng=np.random.default_rng(9437);array=np.asarray(values)
            boot=array[rng.integers(0,len(array),(4096,len(array)))].mean(axis=1)
            for a,b in zip(np.quantile(boot,[.025,.975]),declared['ci95_pct']):close(float(a),b,'control CI')
        pairs[label]={'structural_arithmetic_lifetime':'PASS','static_gain_pct':source['effects']['static_compiler_residency_gain_pct']['mean_pct'],
                      'resident_B0_gain_pct':source['effects']['resident_B0_vs_resident_S_gain_pct']['mean_pct'],
                      'resident_B2_gain_pct':source['effects']['resident_B2_vs_resident_S_gain_pct']['mean_pct']}
    assert total_checked==result['total_executions_audited']
    output={'status':'PASS','configurations':len(pairs),'all_run_audit_count_checked':total_checked,
            'saved_traces_replayed':len(checked),'request_events_replayed':sum(c['requests'] for c in checked),
            'control_hash':manifest['control_source_sha256'],'configuration_results':pairs,'traces':checked,
            'scope':'posthoc compiler residency control with fresh seeds; structural equivalence and timed request replay; no new numerical payload execution or full-model RF residency claim'}
    (root/'resident_control_independent_audit.json').write_text(json.dumps(output,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in output.items() if k!='traces'},indent=2))


if __name__=='__main__':main()
