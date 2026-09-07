"""Freeze the R7 measurement source subtask; no device operations."""
from pathlib import Path
import datetime
import hashlib
import json
import tarfile

ROOT = Path(__file__).resolve().parent
SHA = '42cba83aee86b253c49eccd484646e91d062468d'


def main():
    target = ROOT / 'source_manifest.json'
    if target.exists():
        raise SystemExit('manifest already frozen; do not overwrite')
    with tarfile.open(ROOT / 'xrt_exact.tar.gz', 'r:gz') as archive:
        source_bytes = {m.name.split('/', 1)[1]: archive.extractfile(m).read()
                        for m in archive.getmembers() if m.isfile()}
    records = []
    matched = 0
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or path == target:
            continue
        rel = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        rec = {'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        if rel.startswith(('xrt/', 'raw/src/')):
            original = rel.split('/', 1)[1]
            if original not in source_bytes or data != source_bytes[original]:
                raise SystemExit('source does not match exact archive: ' + rel)
            rec['url'] = f'https://github.com/Xilinx/XRT/blob/{SHA}/{original}'
            rec['matches_exact_archive'] = True
            matched += 1
        records.append(rec)
    manifest = {'frozen_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'source_revision': SHA, 'evidence_level': 'primary source and static local binary inspection',
                'device_calls': 0, 'profiling_enabled': False,
                'exact_archive_verified_files': matched, 'files': records}
    target.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(records), 'exact_archive_verified_files': matched,
                      'manifest_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
