"""Run one bounded, explicitly supplied local diagnostic and retain raw evidence."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command or not args.name.replace('_', '').replace('-', '').isalnum():
        parser.error('supply safe unique name and explicit command')
    target = ROOT / 'evidence' / args.name
    target.mkdir(parents=True, exist_ok=False)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    begin = time.perf_counter()
    timed_out = False
    try:
        p = subprocess.run(args.command, capture_output=True, timeout=args.timeout)
        stdout, stderr, returncode = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        stdout, stderr, returncode = e.stdout or b'', e.stderr or b'', None
        timed_out = True
    except OSError as e:
        stdout, stderr, returncode = b'', str(e).encode('utf8'), None
    elapsed = time.perf_counter() - begin
    (target / 'stdout.bin').write_bytes(stdout)
    (target / 'stderr.bin').write_bytes(stderr)
    for name, data in [('stdout', stdout), ('stderr', stderr)]:
        encoding = 'utf-16-le' if data.count(b'\0') > len(data) / 8 else 'utf8'
        (target / f'{name}.txt').write_text(data.decode(encoding, errors='replace'), encoding='utf8')
    plan = ROOT / 'experiment_plan.md'
    record = dict(command=args.command, started_utc=started,
                  ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  host_process_elapsed_s=elapsed, returncode=returncode,
                  timed_out=timed_out, timeout_s=args.timeout,
                  evidence_level='raw local diagnostic; not NPU kernel timing',
                  plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
                  raw_sha256={n: hashlib.sha256((target/n).read_bytes()).hexdigest()
                              for n in ['stdout.bin', 'stderr.bin']})
    (target/'receipt.json').write_text(json.dumps(record, indent=2), encoding='utf8')
    print(json.dumps(record, indent=2))
    print(stdout.decode('utf8', errors='replace'))
    print(stderr.decode('utf8', errors='replace'))

if __name__ == '__main__':
    main()
