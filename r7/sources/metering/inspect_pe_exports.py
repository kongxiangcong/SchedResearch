"""Read PE export tables from files; never load or execute a DLL."""
from pathlib import Path
import datetime
import hashlib
import json
import struct


def exports(path: Path) -> dict:
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe+4] == b'PE\0\0'
    machine, count, _, _, _, optsize, _ = struct.unpack_from('<HHIIIHH', data, pe+4)
    opt = pe + 24
    magic = struct.unpack_from('<H', data, opt)[0]
    dd = opt + (112 if magic == 0x20b else 96)
    erva, esize = struct.unpack_from('<II', data, dd)
    sects = []
    for i in range(count):
        off = opt + optsize + 40*i
        vs, va, rs, rp = struct.unpack_from('<IIII', data, off+8)
        sects.append((va, max(vs, rs), rp))

    def offset(rva):
        for va, size, raw in sects:
            if va <= rva < va + size:
                return raw + rva-va
        raise ValueError(f'Unmapped RVA {rva:x}')

    names = []
    functions = {}
    if erva:
        exp = struct.unpack_from('<IIHHIIIIIII', data, offset(erva))
        names_count, names_rva = exp[7], exp[9]
        for i in range(names_count):
            noff = offset(struct.unpack_from('<I', data, offset(names_rva)+4*i)[0])
            name = data[noff:data.index(b'\0', noff)].decode('ascii')
            names.append(name)
            ordinal_index = struct.unpack_from('<H', data, offset(exp[10])+2*i)[0]
            function_rva = struct.unpack_from('<I', data, offset(exp[8])+4*ordinal_index)[0]
            if name.startswith(('xcl', 'xrtIni')):
                foff = offset(function_rva)
                functions[name] = {'rva': hex(function_rva), 'file_offset': hex(foff),
                                   'first_32_bytes_hex': data[foff:foff+32].hex(),
                                   'is_forwarder': erva <= function_rva < erva+esize}
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'machine': hex(machine), 'export_count': len(names), 'exports': names,
            'c_functions_code_prefixes': functions}


if __name__ == '__main__':
    root = Path(r'C:\Windows\System32\AMD')
    dlls = ['xrt_coreutil.dll', 'xrt_core.dll', 'amd_xrt_core.dll', 'trace-logging.dll',
            'trace-logging-aks.dll', 'vart-trace.dll']
    out = {'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'method': 'static PE export table parsing; no LoadLibrary or API calls',
           'dlls': [exports(root/name) for name in dlls]}
    Path(__file__).with_name('local_pe_exports.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    for dll in out['dlls']:
        print(dll['path'], dll['export_count'])
        for name in dll['exports']:
            if any(s in name.lower() for s in ['profil', 'trace', 'counter', 'timestamp', 'clock', 'aie', 'debug', 'nop', 'ini']):
                print(' ',name)
