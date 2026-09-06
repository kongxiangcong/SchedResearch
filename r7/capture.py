"""Bounded R7 subprocess evidence; refuses overwrites and retains partial output."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parent
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',required=True)
    p.add_argument('--timeout',type=int,default=90)
    p.add_argument('--cwd')
    p.add_argument('--prepend-path')
    p.add_argument('--xrt-ini')
    p.add_argument('--artifact',action='append',default=[])
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args()
    assert a.command and a.name.replace('_','').replace('-','').isalnum()
    target=ROOT/'evidence'/a.name
    target.mkdir(parents=True,exist_ok=False)
    before={str(Path(x).resolve()):digest(Path(x)) for x in a.artifact}
    if a.xrt_ini: before[str(Path(a.xrt_ini).resolve())]=digest(Path(a.xrt_ini))
    receipt=dict(command=a.command,cwd=str(Path(a.cwd or '.').resolve()),started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),plan_sha256=digest(ROOT/'experiment_plan.md'),artifact_sha256_before=before,timeout_s=a.timeout,child_path_prepend=a.prepend_path,capture_sha256=digest(Path(__file__)))
    (target/'started.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    begin=time.perf_counter()
    try:
        child_env=os.environ.copy()
        if a.prepend_path: child_env['PATH']=a.prepend_path+os.pathsep+child_env.get('PATH','')
        if a.xrt_ini:
            if child_env.get('XCL_EMULATION_MODE'): raise OSError('Refusing physical probe with XCL_EMULATION_MODE set')
            child_env['XRT_INI_PATH']=str(Path(a.xrt_ini).resolve())
        receipt['xrt_environment']={key:child_env.get(key) for key in ['XCL_EMULATION_MODE','XILINX_XRT','XRT_INI_PATH','Debug.native_xrt_trace','Debug.aie_profile','Debug.ml_timeline','Debug.profile','Debug.timeline_trace']}
        (target/'started.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        out=subprocess.run(a.command,cwd=a.cwd,env=child_env,capture_output=True,timeout=a.timeout)
        stdout,stderr,code,timeout=out.stdout,out.stderr,out.returncode,False
    except subprocess.TimeoutExpired as e:
        stdout,stderr,code,timeout=e.stdout or b'',e.stderr or b'',None,True
    except OSError as e:
        stdout,stderr,code,timeout=b'',str(e).encode(),None,False
    receipt.update(host_process_elapsed_s=time.perf_counter()-begin,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),returncode=code,timed_out=timeout)
    for name,data in [('stdout',stdout),('stderr',stderr)]:
        (target/(name+'.bin')).write_bytes(data)
        (target/(name+'.txt')).write_text(data.decode('utf8',errors='replace'),encoding='utf8')
    receipt['raw_sha256']={n:digest(target/n) for n in ['stdout.bin','stderr.bin']}
    receipt['artifact_sha256_after']={x:digest(Path(x)) for x in before}
    receipt['artifacts_unchanged']=receipt['artifact_sha256_after']==before
    (target/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt,indent=2))
    print(stdout.decode('utf8',errors='replace'))
    print(stderr.decode('utf8',errors='replace'))
    raise SystemExit(0 if code==0 and not timeout and receipt['artifacts_unchanged'] else 1)

if __name__=='__main__': main()
