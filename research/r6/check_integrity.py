"""Verify R6 plus explicit parent snapshot mapping; never refreeze R4/R5."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT/'r6'
MANIFEST = ROUND/'artifact_integrity.json'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def json_read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def verify_parents():
    lineage = json_read(ROUND/'history_lineage.json')
    for parent in lineage['parent_manifests']:
        assert digest(ROOT/parent['path']) == parent['sha256'], parent['path']
    old = json_read(ROOT/'r5/artifact_integrity.json')['sha256']
    for logical, expected in old.items():
        physical = lineage['r5_progress_snapshot']['path'] if logical == 'research_progress.md' else logical
        assert digest(ROOT/physical) == expected, {'parent':'R5','logical':logical,'physical':physical}
    old_r4 = json_read(ROOT/'experiments/results/r4/artifact_integrity.json')['artifact_sha256']
    for path, expected in old_r4.items():
        assert digest(ROOT/path) == expected, {'parent':'R4','path':path}
    assert digest(ROOT/'research_progress.md') == lineage['successor_progress']['sha256']
    assert digest(ROOT/lineage['r5_progress_snapshot']['path']) == lineage['r5_progress_snapshot']['sha256']
    assert lineage['r5_progress_snapshot']['sha256'] == old['research_progress.md']
    assert lineage['successor_progress']['parent_sha256'] == old['research_progress.md']
    assert lineage['successor_progress']['sha256'] != old['research_progress.md']
    snapshot = (ROOT/lineage['r5_progress_snapshot']['path']).read_text(encoding='utf8')
    successor = (ROOT/'research_progress.md').read_text(encoding='utf8')
    for row in snapshot.splitlines():
        if row.startswith('| R'):
            assert row in successor.splitlines(), 'historical row changed'
    return {'r4_paths':len(old_r4),'r5_paths_via_explicit_snapshot':len(old),'historical_rows_preserved':True}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze-r6',action='store_true')
    args = parser.parse_args()
    parents = verify_parents()
    paths = [p for p in ROUND.rglob('*') if p.is_file() and '__pycache__' not in p.parts
             and p.suffix != '.pyc' and p != MANIFEST]
    paths.append(ROOT/'research_progress.md')
    actual = {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(paths)}
    if args.freeze_r6:
        if MANIFEST.exists():
            raise SystemExit('Refusing to overwrite a frozen R6 manifest; record a successor instead.')
        MANIFEST.write_text(json.dumps({'status':'FROZEN','scope':'R6 files and successor progress; no device-performance acceptance',
                                       'parent_verification':parents,'sha256':actual},indent=2),encoding='utf8')
    else:
        expected = json_read(MANIFEST)['sha256']
        assert actual == expected, {'missing':sorted(set(expected)-set(actual)),
                                    'new':sorted(set(actual)-set(expected)),
                                    'changed':[p for p in actual if p in expected and actual[p] != expected[p]]}
    print(json.dumps({'status':'PASS','operation':'freeze-r6' if args.freeze_r6 else 'verify',
                      'r6_and_progress_paths':len(actual),**parents}))

if __name__ == '__main__':
    main()
