"""Explicit bounded launch entry point. Never upgrades or changes system files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('kernel',choices=['copy','compute'])
    p.add_argument('phase',choices=['initial','repeat'])
    a=p.parse_args()
    executable=ROOT/'bin'/(a.kernel+'_probe.exe')
    source=ROOT/(a.kernel+'_probe.cpp')
    # Build receipts include source snapshots; refuse stale binary/source pairs.
    candidates=[]
    for receipt in (ROOT/'sdk').glob('*receipt*.json'):
        value=json.loads(receipt.read_text(encoding='utf8'))
        if isinstance(value,list): candidates.extend(x for x in value if isinstance(x,dict))
    matches=[x for x in candidates if x.get('name')==a.kernel and x.get('source_sha256')==sha(source) and x.get('artifact_sha256')==sha(executable) and x.get('exit_code')==0]
    if not matches: raise SystemExit('No successful build receipt binds current source and binary')
    name=a.kernel+'_'+a.phase
    if a.phase=='repeat':
        initial=json.loads((ROOT/'evidence'/(a.kernel+'_initial')/'receipt.json').read_text())
        if initial['returncode']!=0 or initial['timed_out']:raise SystemExit('Initial execution did not pass')
        events=[json.loads(line) for line in (ROOT/'evidence'/(a.kernel+'_initial')/'stdout.txt').read_text().splitlines() if line.startswith('{')]
        if len([e for e in events if e.get('stage')=='result' and e.get('numeric_pass')])!=1:raise SystemExit('Initial numerical acceptance missing')
    amd=Path('C:/Windows/System32/AMD')
    artifacts=[source,executable,ROOT/'run_calibration.py',ROOT/'compute_addendum.md',amd/'xrt_coreutil.dll',amd/'xrt_core.dll',amd/'amd_xrt_core.dll']
    repetitions='1' if a.phase=='initial' else '3'
    if a.kernel=='copy':
        xb=amd/'validate_phx.xclbin';instruction=amd/'DPU_Sequence/df_bw_dpu.txt';artifacts.extend([xb,instruction])
        command=[str(executable),str(xb),str(instruction),repetitions]
    else:
        xb=ROOT/'sources/kernel_access/ryzenai/example/transformers/xclbin/phx/gemm_4x4.xclbin'
        fixture=ROOT/'sources/kernel_access/int8_fixture'
        artifacts.extend([xb,*sorted(fixture.glob('*.bin')),fixture/'fixture_manifest.json',ROOT/'sdk/fixture_verification_output.txt'])
        command=[str(executable),str(xb),str(fixture),repetitions,str(ROOT/'evidence'/(name+'_outputs'))]
    capture=[sys.executable,'-X','utf8','-B',str(ROOT/'capture.py'),'--name',name,'--timeout','90','--cwd',str(ROOT),'--prepend-path',str(amd),'--xrt-ini',str(ROOT/'sources/metering/configs/host_screening_off.ini')]
    for artifact in artifacts: capture.extend(['--artifact',str(artifact)])
    completed=subprocess.run(capture+command)
    raise SystemExit(completed.returncode)

if __name__=='__main__': main()
