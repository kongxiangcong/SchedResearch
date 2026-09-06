"""Read PE exports and fetch exact XRT public ABI. No device execution."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import struct
import urllib.request

ROOT = Path(__file__).resolve().parent
SHA = '42cba83aee86b253c49eccd484646e91d062468d'

def exports(path):
    data = path.read_bytes()
    pe, = struct.unpack_from('<I', data, 0x3c)
    assert data[pe:pe+4] == b'PE\0\0'
    machine, sections, _, _, _, optional_size, _ = struct.unpack_from('<HHIIIHH', data, pe+4)
    opt = pe+24
    assert struct.unpack_from('<H', data, opt)[0] == 0x20b
    export_rva, export_size = struct.unpack_from('<II', data, opt+112)
    table = []
    for n in range(sections):
        off = opt+optional_size+n*40
        virtual_size, rva, raw_size, raw_offset = struct.unpack_from('<IIII', data, off+8)
        table.append((rva, max(virtual_size, raw_size), raw_offset))
    def offset(rva):
        for start,size,raw in table:
            if start <= rva < start+size:
                return raw+rva-start
        raise ValueError(rva)
    names = []
    if export_rva:
        directory = offset(export_rva)
        count, names_rva = struct.unpack_from('<I', data, directory+24)[0], struct.unpack_from('<I', data, directory+32)[0]
        for n in range(count):
            rva, = struct.unpack_from('<I', data, offset(names_rva)+4*n)
            begin = offset(rva)
            names.append(data[begin:data.index(b'\0', begin)].decode('ascii'))
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), machine=machine, exports=names)

def main():
    evidence = ROOT/'evidence'
    evidence.mkdir(exist_ok=True)
    report = [exports(Path('C:/Windows/System32/AMD')/name) for name in ['xrt_coreutil.dll','xrt_core.dll','amd_xrt_core.dll']]
    (evidence/'runtime_exports.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    for r in report:
        print(r['path'], *[x for x in r['exports'] if x.startswith(('xrt','xcl'))],sep='\n')
    dest = ROOT/'sources'/'abi'
    dest.mkdir(parents=True,exist_ok=True)
    manifest = []
    paths = ['core/include/xrt/'+name for name in ['xrt_device.h','xrt_kernel.h','xrt_bo.h','xrt_xclbin.h','xrt_hw_context.h']]
    paths += ['core/common/api/'+name for name in ['xrt_device.cpp','xrt_kernel.cpp','xrt_bo.cpp','xrt_hw_context.cpp']]
    paths += ['core/include/xrt.h','core/include/xclbin.h','core/include/ert.h']
    for path in paths:
        url = f'https://raw.githubusercontent.com/Xilinx/XRT/{SHA}/src/runtime_src/{path}'
        row = dict(url=url, revision=SHA, accessed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        try:
            data=urllib.request.urlopen(url,timeout=30).read()
            target=dest/Path(path).name
            target.write_bytes(data)
            row.update(path=target.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),status='saved')
        except Exception as e:
            row.update(status='failed',error=str(e))
        manifest.append(row)
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    main()
