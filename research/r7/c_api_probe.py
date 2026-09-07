"""Inspect documented XRT C API device/load path, without submitting a kernel."""
import ctypes as C
import json
import os
from pathlib import Path
import sys

def event(**x): print(json.dumps(x),flush=True)
def main():
    amd=Path('C:/Windows/System32/AMD')
    directory=os.add_dll_directory(str(amd))
    lib=C.CDLL(str(amd/'xrt_coreutil.dll'),use_errno=True)
    def bind(name,ret,args):
        fn=getattr(lib,name); fn.restype=ret; fn.argtypes=args; return fn
    opening=bind('xrtDeviceOpen',C.c_void_p,[C.c_uint])
    close=bind('xrtDeviceClose',C.c_int,[C.c_void_p])
    load=bind('xrtDeviceLoadXclbinFile',C.c_int,[C.c_void_p,C.c_char_p])
    event(stage='dll_loaded')
    dev=opening(0)
    event(stage='device_open',handle=dev,errno=C.get_errno())
    if not dev: return 2
    try:
        if '--load' in sys.argv:
            rc=load(dev,str(amd/'validate_phx.xclbin').encode())
            event(stage='load_xclbin_file',returncode=rc,errno=C.get_errno(),kernel_submitted=False)
            if rc!=0: return 3
    finally:
        event(stage='device_close',returncode=close(dev))
    return 0

if __name__=='__main__': raise SystemExit(main())
