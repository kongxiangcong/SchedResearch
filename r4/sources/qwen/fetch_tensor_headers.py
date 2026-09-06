"""Read the JSON metadata prefixes of safetensors; never read tensor payloads."""
import datetime, hashlib, json, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REV = '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'


def main():
    index=json.loads((ROOT/'model.safetensors.index.json').read_text())
    records=[]; tensors={}
    for i,shard in enumerate(sorted(set(index['weight_map'].values()))):
        url=f'https://huggingface.co/Qwen/Qwen3.5-4B/resolve/{REV}/{shard}'
        # Read the stream only as far as the specified safetensors header end.
        # Tensor values are neither requested with a full-body read nor saved.
        req=urllib.request.Request(url,headers={'User-Agent':'SchedResearch-R4-header-metadata'})
        with urllib.request.urlopen(req,timeout=60) as response:
            first=response.read(8)
            size=int.from_bytes(first,'little')
            if size<=0 or size>2_000_000:raise ValueError(('unexpected header length',size))
            header=response.read(size)
            if len(header)!=size:raise ValueError('truncated JSON metadata header')
        obj=json.loads(header)
        out=f'shard_{i+1}_safetensors_header.json'
        (ROOT/out).write_bytes(header)
        records.append({'file':out,'url':url,'model_revision':REV,'bytes':len(header),
                        'sha256':hashlib.sha256(header).hexdigest(),'stream_bytes_read':8+size,
                        'contains_tensor_payload':False})
        tensors.update({k:v for k,v in obj.items() if k!='__metadata__'})
        print(out,size)
    import math,collections
    counts=collections.defaultdict(lambda:collections.Counter())
    for k,v in tensors.items():
        module='.'.join(k.split('.')[:2]) if k.startswith('model.') else 'mtp'
        counts[module][v['dtype']]+=math.prod(v['shape'])
    manifest={'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'files':records,'module_parameter_counts':dict(counts),
              'total_parameters':sum(sum(x.values()) for x in counts.values())}
    (ROOT/'tensor_header_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest['module_parameter_counts'],indent=2))


if __name__=='__main__':main()
