import pathlib,hashlib,json,datetime
r=pathlib.Path('r7/sources/kernel_access');records=[]
for p in [pathlib.Path('C:/Windows/System32/AMD/aieml_gemm_vm_phx_4x4.xclbin'),pathlib.Path('C:/Windows/System32/AMD/aieml_gemm_vm_phx_4x4_bf16.xclbin'),pathlib.Path('C:/Windows/System32/AMD/aieml_gemm_vm_phx_4x4_bf16.json')]:
 b=p.read_bytes();record={'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 if p.suffix=='.json':q=r/'installed_bf16_aie_metadata.json';q.write_bytes(b);record['frozen_copy']=str(q)
 records.append(record)
(r/'local_installed_assets.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'assets':records},indent=2),encoding='utf-8')
print(json.dumps(records,indent=2))
