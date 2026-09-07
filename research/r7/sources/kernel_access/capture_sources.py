import subprocess,pathlib,json,hashlib,datetime
root=pathlib.Path('r7/sources/kernel_access')
sets={
'riallto':['README.md','npu/runtime/apprunner.py','tests/test_endtoend.py','tests/test_applications.py','scripts/utils/setup_runtime.ps1','setup.py','npu/lib/kernels/cpp/plus1.cpp','npu/lib/applications/binaries/color_threshold_v1_720p.seq','npu/lib/applications/binaries/color_threshold_v1_720p.json','npu/lib/applications/color_threshold.py'],
'ryzenai':['README.md','example/transformers/README.md','example/transformers/ops/cpp/qlinear_2/qlinear_2.hpp','example/transformers/ops/cpp/utils/dpu_kernel_metadata.hpp','example/transformers/ops/cpp/utils/super_instr.h','example/transformers/tests/cpp/test_qlinear_2.cpp','example/transformers/third_party/xrt-ipu/xrt/include/xrt/xrt_kernel.h','example/transformers/third_party/xrt-ipu/xrt/include/xrt/xrt_bo.h','example/transformers/third_party/xrt-ipu/xrt/include/xrt/xrt_device.h','example/transformers/third_party/xrt-ipu/xrt/include/xrt/xrt_version.h','example/transformers/ops/cpp/utils/xrt_context.hpp'],
'dynamicdispatch':['README.md','VERSION','src/ops/matmul/matmul.cpp','src/ops/ops_common/matmul_matrix.hpp','tests/cpp/unit_tests/test_matmul.cpp']}
manifest=[]
for repo,files in sets.items():
 sha=subprocess.check_output(['git','-C',str(root/f'{repo}_repo'),'rev-parse','HEAD'],text=True).strip()
 owner={'riallto':'AMDResearch/Riallto','ryzenai':'amd/RyzenAI-SW','dynamicdispatch':'amd/DynamicDispatch'}[repo]
 for f in files:
  p=root/repo/f;p.parent.mkdir(parents=True,exist_ok=True)
  r=subprocess.run(['git','-C',str(root/f'{repo}_repo'),'show',f'{sha}:{f}'],capture_output=True)
  m={'repo':owner,'revision':sha,'source_path':f,'url':f'https://github.com/{owner}/blob/{sha}/{f}','local_path':str(p),'exit_code':r.returncode}
  if r.returncode==0:p.write_bytes(r.stdout);m.update(sha256=hashlib.sha256(r.stdout).hexdigest(),bytes=len(r.stdout))
  else:m['error']=r.stderr.decode('utf-8',errors='replace')
  manifest.append(m)
  print(repo,f,r.returncode,len(r.stdout))
(root/'source_manifest.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'items':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
