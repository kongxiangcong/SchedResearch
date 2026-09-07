"""Freeze SDK assembly/build evidence without including device-run results."""
from pathlib import Path
import datetime
import hashlib
import json

BASE = Path(__file__).resolve().parent
R7 = BASE.parent
stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
def entry(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(R7)).replace("\\", "/"), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}

fixture = R7 / "sources/kernel_access/int8_fixture"
fixture_receipt = {
    "recorded_utc": stamp,
    "command": [str(BASE / "verify_fixture.exe"), str(fixture)],
    "exit_code": 0,
    "evidence_level": "CPU-only check using frozen original AMD C++ packing/sequence helpers plus independent INT64 oracle",
    "stdout": entry(BASE / "fixture_verification_output.txt"),
    "executable": entry(BASE / "verify_fixture.exe"),
    "inputs": [entry(fixture / n) for n in ["super_sequence.bin", "weights_rowmajor_int8.bin",
                                             "weights_packed_int8.bin", "a_rowmajor_int8.bin",
                                             "expected_rowmajor_int32.bin"]],
    "device_executed": False
}
(BASE / "fixture_verification_receipt.json").write_text(json.dumps(fixture_receipt, indent=2) + "\n", encoding="utf-8")
files = [p for p in BASE.rglob("*") if p.is_file() and p.name != "artifact_manifest.json"]
files.append(R7 / "sdk_build_report.md")
receipt = {"recorded_utc": stamp, "scope": "SDK assembly, build and host metadata/CPU fixture evidence only",
           "files": [entry(p) for p in sorted(files)]}
(BASE / "artifact_manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(files), "created_utc": stamp}))
