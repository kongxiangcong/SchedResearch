import pathlib,re,json,hashlib
r=pathlib.Path('r7/sources/kernel_access');p=r/'ryzenai/example/transformers/xclbin/phx/gemm_4x4.xclbin';b=p.read_bytes()
for i,m in enumerate(re.finditer(rb'<\?xml.*?</project>',b,re.S)):
 out=r/f'gemm_4x4_embedded_{i}.xml';out.write_bytes(m.group());print(out,len(m.group()))
for m in re.finditer(rb'<kernel\b[^>]*>.*?</kernel>',b,re.S):print(m.group().decode('utf-8',errors='replace')[:11000])
