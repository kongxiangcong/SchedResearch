import json,urllib.request,pathlib,hashlib,datetime
root=pathlib.Path('r7/sources/kernel_access')
repos=[('riallto','AMDResearch/Riallto','8e73ab69daf2f04f1341baf6181a8d2ab478848d'),('ryzenai','amd/RyzenAI-SW','a3d163c81e4d0b21667c05f614c1d79be14c3fa1'),('dynamicdispatch','amd/DynamicDispatch','b3051f03e20aab237cda3bbe4cd2081f76b72b06')]
for name,repo,sha in repos:
 url=f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1'
 try:
  data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'r7-primary-source'}),timeout=25).read()
  (root/f'{name}_tree.json').write_bytes(data)
  j=json.loads(data)
  print(name,len(j.get('tree',[])),j.get('truncated'), hashlib.sha256(data).hexdigest())
  for e in j.get('tree',[]):
   p=e['path']
   if any(s in p.lower() for s in ('matmul','gemm','vectoradd','vector_add','plusone','plus_one','.seq','xclbin')):print(p)
 except Exception as e:print(name,repr(e))
