import pathlib,subprocess,urllib.request,json,hashlib,datetime,concurrent.futures
root=pathlib.Path('r7/sources/kernel_access');mfile=root/'source_manifest.json'
m=json.loads(mfile.read_text(encoding='utf-8'))
repo='amd/RyzenAI-SW';sha='a3d163c81e4d0b21667c05f614c1d79be14c3fa1'
files=['example/transformers/README.MD','example/transformers/third_party/xrt-ipu/xrt/include/version.h','example/transformers/third_party/xrt-ipu/xrt/version.json','example/transformers/ops/cpp/utils/wgt_matrix.h','example/transformers/ops/cpp/utils/buffer_ops.h','example/transformers/ops/cpp/utils/ml_params.h','example/transformers/dll/phx/qlinear_2/mc_code_1_2k_2k.txt','example/transformers/xclbin/phx/gemm_4x4.xclbin','example/transformers/xclbin/phx/aieml_gemm_vm_phx_4x4.xclbin','example/transformers/ops/cpp/qlinear/qlinear.hpp','example/transformers/third_party/.tvm/aie/aieml_gemm_vm_phx_4x4_bf16.json']
def capture(f):
 url=f'https://raw.githubusercontent.com/{repo}/{sha}/{f}';p=root/'ryzenai'/f;p.parent.mkdir(parents=True,exist_ok=True)
 e={'repo':repo,'revision':sha,'source_path':f,'url':url,'local_path':str(p)}
 try:
  data=urllib.request.urlopen(url,timeout=30).read();p.write_bytes(data);e.update(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),lfs_pointer=data.startswith(b'version https://git-lfs.github.com'),exit_code=0)
 except Exception as err:e.update(exit_code=1,error=repr(err))
 return e
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
 for e in pool.map(capture,files):m['items'].append(e);print(e['source_path'],e.get('bytes'),e.get('lfs_pointer'),e.get('error'))
m['captured_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();mfile.write_text(json.dumps(m,indent=2),encoding='utf-8')
