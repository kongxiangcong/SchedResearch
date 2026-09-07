"""Freeze old code and results hashes before any R4 development."""
from pathlib import Path
import hashlib
import json
import shutil


def main():
    root = Path(__file__).resolve().parents[1]
    dest = root / 'r4' / 'r3_snapshot'
    manifest_path = dest / 'manifest.json'
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text())
        for rel, digest in data['sources'].items():
            assert hashlib.sha256((dest / rel).read_bytes()).hexdigest() == digest
        print('Existing R3 snapshot verified; never overwritten.')
        return
    files = [root / 'README.md']
    for folder in ('sim', 'tests', 'experiments'):
        files += [p for p in (root / folder).rglob('*.py') if '__pycache__' not in p.parts]
    files += list((root / 'r3').glob('*.md'))
    sources = {}
    for p in files:
        rel = p.relative_to(root).as_posix()
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        sources[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    results = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (root / 'experiments' / 'results').rglob('*') if p.is_file()}
    manifest_path.write_text(json.dumps({'sources': sources, 'prior_results': results,
        'note': 'Copies source/README/R3 reports; prior results remain at original paths unchanged.'}, indent=2))
    print(f'Frozen {len(sources)} source/report files; hashed {len(results)} prior artifacts.')


if __name__ == '__main__':
    main()
