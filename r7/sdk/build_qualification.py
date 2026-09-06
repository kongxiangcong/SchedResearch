"""Build receipts capture immutable source bytes with each artifact. No device runs."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys

BASE = Path(__file__).resolve().parent
R7 = BASE.parent

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

receipt_path = BASE / "build_receipt.json"
if receipt_path.exists():
    previous = receipt_path.read_bytes()
    history = BASE / "build_history" / hashlib.sha256(previous).hexdigest()[:16]
    history.mkdir(parents=True, exist_ok=True)
    (history / "build_receipt.json").write_bytes(previous)
    for prior in json.loads(previous):
        for filename in [f'{prior["name"]}_source_at_build.cpp', f'build_{prior["name"]}_output.txt']:
            source = BASE / filename
            if source.exists():
                (history / filename).write_bytes(source.read_bytes())

selected = set(sys.argv[1:]) or {"copy", "compute", "fixture"}
assert selected <= {"copy", "compute", "fixture"}, "Unknown build target"
records = [r for r in json.loads(receipt_path.read_text()) if r["name"] not in selected] if receipt_path.exists() else []
for name, source, target in [
    ("copy", R7 / "copy_probe.cpp", R7 / "bin/copy_probe.exe"),
    ("compute", R7 / "compute_probe.cpp", R7 / "bin/compute_probe.exe"),
    ("fixture", R7 / "sources/kernel_access/verify_fixture.cpp", BASE / "verify_fixture.exe")
]:
    if name not in selected:
        continue
    original = source.read_bytes()
    (BASE / f"{name}_source_at_build.cpp").write_bytes(original)
    script = BASE / f"build_{name}.cmd"
    result = subprocess.run([str(script)], capture_output=True, timeout=60)
    assert original == source.read_bytes(), f"{source} changed during compilation"
    log = BASE / f"build_{name}_output.txt"
    log.write_bytes(result.stdout + b"\nSTDERR\n" + result.stderr)
    record = {"name": name, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "source": str(source), "source_sha256": hashlib.sha256(original).hexdigest(),
              "build_script": str(script), "script_sha256": sha256(script),
              "exit_code": result.returncode, "artifact": str(target),
              "artifact_sha256": sha256(target) if result.returncode == 0 else None,
              "device_executed": False, "build_log": str(log)}
    records.append(record)
    print(json.dumps(record))
    if result.returncode:
        print(log.read_bytes().decode("utf-8", "replace"))
        break
receipt_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
