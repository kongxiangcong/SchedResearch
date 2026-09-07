"""Bounded metadata-only dynamic-link checks; never opens an XRT device."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess

BASE = Path(__file__).resolve().parent
R7 = BASE.parent
EXE = BASE / "xclbin_metadata.exe"
env = os.environ.copy()
env["PATH"] = r"C:\Windows\System32\AMD" + os.pathsep + env.get("PATH", "")
files = sorted(Path(r"C:\Windows\System32\AMD").glob("*.xclbin"))
files.append(R7 / "sources/kernel_access/ryzenai/example/transformers/xclbin/phx/gemm_4x4.xclbin")
records = []
outdir = BASE / "metadata"
outdir.mkdir(exist_ok=True)
for index, path in enumerate(files):
    result = subprocess.run([str(EXE), str(path)], env=env, capture_output=True, timeout=20)
    output = result.stdout.decode("utf-8", "replace")
    errors = result.stderr.decode("utf-8", "replace")
    loaded_lines = [line for line in output.splitlines() if line.startswith("loaded_xrt_coreutil ")]
    loaded_dll = json.loads(loaded_lines[0].split(" ", 1)[1]) if loaded_lines else None
    output_path = outdir / f"{index:02d}_{path.stem}.txt"
    output_path.write_text(output + ("\nSTDERR\n" + errors if errors else ""), encoding="utf-8")
    records.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "exit_code": result.returncode, "device_opened": False,
                    "loaded_dll_path": loaded_dll,
                    "loaded_dll_sha256": hashlib.sha256(Path(loaded_dll).read_bytes()).hexdigest() if loaded_dll else None,
                    "output": str(output_path.relative_to(R7)).replace("\\", "/"),
                    "kernel_lines": [line for line in output.splitlines() if line.startswith("kernel ")],
                    "has_XDP_KERNEL": 'kernel "XDP_KERNEL"' in output})
receipt = {"created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "executable_sha256": hashlib.sha256(EXE.read_bytes()).hexdigest(),
           "environment_change": "PATH prepended C:/Windows/System32/AMD only in child subprocess environment",
           "records": records}
(BASE / "metadata_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(records, indent=2))
