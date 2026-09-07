"""Freeze/verify the delivered R5 evidence snapshot without editing R1–R4."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import numpy as np


ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'artifact_integrity.json'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    paths=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p!=MANIFEST]
    paths.append(ROOT.parent/'research_progress.md')
    actual={p.relative_to(ROOT.parent).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    if args.freeze:
        record={'status':'FROZEN','sha256':actual,'python':platform.python_version(),'numpy':np.__version__,
            'scope':'R5 files and cross-round progress table; no R1-R4 rewrite, no device validation'}
        MANIFEST.write_text(json.dumps(record,indent=2),encoding='utf8')
    else:
        record=json.loads(MANIFEST.read_text(encoding='utf8'))
        assert actual==record['sha256'], {'missing':sorted(set(record['sha256'])-set(actual)),
            'new':sorted(set(actual)-set(record['sha256'])),
            'changed':[k for k in actual if k in record['sha256'] and actual[k]!=record['sha256'][k]]}
    print(json.dumps({'status':'PASS','files':len(actual),'operation':'freeze' if args.freeze else 'verify'}))


if __name__=='__main__':main()
