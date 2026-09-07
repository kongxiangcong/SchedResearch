"""Read-only diagnosis of a preregistered deterministic source comparison.

No new scheduling intervention, mechanism tuning or performance execution.
"""
from pathlib import Path
import gzip
import hashlib
import json


def main():
    root=Path(__file__).resolve().parent
    directory=root/'results'
    case='request__flux_projection__ref_none'
    files={tag:directory/f'{case}__2000__{tag}.json.gz' for tag in ('S','B0')}
    traces={tag:json.load(gzip.open(path,'rt',encoding='utf8')) for tag,path in files.items()}
    byid={tag:{r['task']:r for r in data['commands']} for tag,data in traces.items()}
    ordered={tag:sorted(data['commands'],key=lambda r:r['sequence']) for tag,data in traces.items()}
    first=next(i for i,(a,b) in enumerate(zip(ordered['S'],ordered['B0'])) if a['task']!=b['task'])
    assert traces['S']['environment']['mode']==traces['B0']['environment']['mode']=='none'
    assert traces['S']['plan']==traces['B0']['plan']
    names=('input','load.c1.k00','load.c1.k01','feed.c0.k00','out1')
    result={'case':case,'status':'trace-supported diagnosis; not an intervention',
        'inputs':{tag:{'file':path.relative_to(root.parent).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for tag,path in files.items()},
        'latency':{tag:data['latency'] for tag,data in traces.items()},
        'late_cycles':traces['B0']['latency']-traces['S']['latency'],
        'first_order_difference_index':first,
        'first_order_difference':{tag:ordered[tag][first] for tag in traces},
        'tracked_commands':{name:{tag:byid[tag][name] for tag in traces} for name in names},
        'external_payload_bytes':{tag:data['metrics']['external_bytes'] for tag,data in traces.items()},
        'external_service_cycles':{tag:data['metrics']['external_service_cycles'] for tag,data in traces.items()},
        'order_opportunity_union':traces['S']['metrics']['task_order_blocked_union'],
        'claim':'With deterministic service, the ready policy starts two core1 weight DMA commands before the still-running shared input load completes. Input completion is 2048 cycles later, and the whole slice is304 cycles slower despite3239 cycles of legal order-wait opportunities. Extra early work competes for the same saturated external service; legal early issue is not guaranteed end-to-end recovery.',
        'limit':'This paired trace identifies request-pressure and changed progress. It does not quantify independent causal contributions of each changed command or prove a different scheduler impossible.'}
    assert result['late_cycles']==304
    assert byid['B0']['input']['visible']-byid['S']['input']['visible']==2048
    assert result['external_payload_bytes']['S']==result['external_payload_bytes']['B0']
    assert result['external_service_cycles']['S']==result['external_service_cycles']['B0']
    (root/'trace_diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('tracked_commands','inputs')},indent=2))


if __name__=='__main__':main()
