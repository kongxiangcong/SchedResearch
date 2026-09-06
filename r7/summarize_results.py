"""Audit actual R7 receipts/output bytes; no device calls and no performance gate."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def audited_run(name):
    base=ROOT/'evidence'/name; receipt=read(base/'receipt.json')
    assert receipt['returncode']==0 and not receipt['timed_out'] and receipt['artifacts_unchanged'],name
    assert receipt['plan_sha256']==sha(ROOT/'experiment_plan.md'),name
    assert receipt['capture_sha256']==sha(ROOT/'capture.py'),name
    assert receipt['artifact_sha256_before']==receipt['artifact_sha256_after'],name
    for p,digest in receipt['artifact_sha256_before'].items():assert sha(Path(p))==digest,p
    for p,digest in receipt['raw_sha256'].items():assert sha(base/p)==digest,p
    assert not (base/'stderr.bin').read_bytes(),name
    env=receipt['xrt_environment'];assert env['XCL_EMULATION_MODE'] is None
    for k in env:
        if k.startswith('Debug.'):assert env[k] is None,k
    raw=(base/'stdout.bin').read_bytes().decode('utf8')
    events=[json.loads(line) for line in raw.splitlines() if line.startswith('{')]
    assert all(not line.strip() or line.startswith('{') for line in raw.splitlines()), 'Unexpected runtime output'
    pre=[e for e in events if e['stage']=='prelaunch_contract'];assert len(pre)==1
    results=[e for e in events if e['stage']=='result']
    completed=[e for e in events if e['stage']=='completed'];assert len(completed)==1
    count=1 if name.endswith('initial') else 3
    assert len(results)==completed[0]['repetitions']==count
    assert [r['iteration'] for r in results]==list(range(count))
    for result in results:
        assert result['state']==4 and result['mismatches']==0 and result['numeric_pass']
        for field in ['host_launch_wait2_s','sync_from_device_s','launch_to_output_sync_s']:
            assert math.isfinite(result[field]) and result[field]>0,field
        assert result['launch_to_output_sync_s']>=result['host_launch_wait2_s']+result['sync_from_device_s']-1e-7
        if name.startswith('compute'):
            output=ROOT/'evidence'/(name+'_outputs')/('output_'+str(result['iteration'])+'.bin')
            oracle=ROOT/'sources/kernel_access/int8_fixture/expected_rowmajor_int32.bin'
            assert output.read_bytes()==oracle.read_bytes()
            assert sha(output)==result['output_sha256'] and result['compared_int32']==2048
            assert result['inputs_unchanged_host_mapping']
        else:
            assert result['compared_words']==268435456 and result['input_unchanged']
            assert result['output_sha256']==pre[0]['input_sha256']
    return dict(name=name,receipt_sha256=sha(base/'receipt.json'),started_utc=receipt['started_utc'],host_process_elapsed_s=receipt['host_process_elapsed_s'],prelaunch_contract=pre[0],results=results)

def main():
    runs=[audited_run(name) for name in ['copy_initial','compute_initial','copy_repeat','compute_repeat']]
    summary=dict(schema_version='r7.access-calibration.v1',fixture=False,
      evidence_level='physical Phoenix direct XRT execution; full numeric checks; host elapsed calibration only',
      runs=runs,counts=dict(copy_launches=4,compute_launches=4,process_invocations=4,confirmation_train=0,confirmation_validation=0,confirmation_test=0,controlled_interference_pairs=0,compiler_variants=0,dynamic_variants=0),
      calibration=dict(known_logical_bytes_copy_functional=True,single_compute_functional=True,host_timer_only=True,device_empty_run=False,actual_bytes_counter=False,compute_active_counter=False,instrumentation_overhead=False),
      unknown={
        'actual_read_bytes':dict(value=None,reason='No actual requested/accepted/completed port observation; BO payloads are logical sizes'),
        'actual_write_bytes':dict(value=None,reason='Same; poison/sync/command traffic is not a bus count'),
        'device_elapsed':dict(value=None,reason='Installed timestamp export is a constant-zero stub; no calibrated device timer'),
        'compute_active':dict(value=None,reason='Selected xclbins lack XDP_KERNEL; required compatible profiler and event definitions absent'),
        'request_latency_outstanding_limits':dict(value=None,reason='No executable observation with accepted/released boundaries'),
        'device_empty_run':dict(value=None,reason='No source-backed zero-work instruction/firmware contract qualified; host timer is not no-op device'),
        'instrumentation_overhead':dict(value=None,reason='No usable device profiler to compare on/off; host timed intervals have not been paired against a minimal instrumentation variant'),
        'runtime_frequency':dict(value=None,reason='No runtime clock trace/lock or thermal control'),
        'strong_static_residual':dict(value=None,reason='Prebuilt functional baseline only; no legal static search/selected contract/controlled background pairs')},
      device_access_accepted=True,host_elapsed_screening_capability=True,full_measurement_calibration_pass=False,
      strong_static_established=False,mechanism_exploration_allowed=False,performance_gate_evaluated=False,
      decision='ACCEPT fixed copy/INT8 GEMM access; REFINE profiling/compiler contracts; R5 ready candidate remains closed')
    (ROOT/'measurement_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['runs','unknown']},indent=2))
    for r in runs:print(r['name'],[x['host_launch_wait2_s'] for x in r['results']])

if __name__=='__main__':main()
