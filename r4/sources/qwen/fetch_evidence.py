"""Fetch only small primary-source artifacts, never model tensor payloads."""
from __future__ import annotations
import datetime, hashlib, json, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = 'Qwen/Qwen3.5-4B'
REV = '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
TF_REV = 'f62dc9bf2c90353b442a56e74391fbb8c689b55e'
FILES = {
    'model_api.json': f'https://huggingface.co/api/models/{MODEL}/revision/{REV}',
    **{f: f'https://huggingface.co/{MODEL}/resolve/{REV}/{f}' for f in
       ('config.json', 'README.md', 'LICENSE', 'model.safetensors.index.json', 'preprocessor_config.json')},
    **{f: f'https://raw.githubusercontent.com/huggingface/transformers/{TF_REV}/src/transformers/models/qwen3_5/{f}' for f in
       ('modeling_qwen3_5.py', 'modular_qwen3_5.py', 'configuration_qwen3_5.py')},
}

def main():
    records = []
    for filename, url in FILES.items():
        req = urllib.request.Request(url, headers={'User-Agent':'SchedResearch-R4-evidence'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read(4_000_001)
            if len(data) > 4_000_000:
                raise ValueError('Small artifact limit exceeded')
            actual_url = resp.geturl()
        (ROOT / filename).write_bytes(data)
        records.append({'file': filename, 'url': url, 'resolved_url': actual_url,
                        'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        print(filename, len(data))
    manifest = {'model_repo': MODEL, 'model_revision': REV, 'transformers_revision': TF_REV,
                'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'tensor_payloads_downloaded': False, 'files': records}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')

if __name__ == '__main__':
    main()
