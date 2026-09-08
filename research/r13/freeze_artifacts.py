"""Freeze compact R13 evidence and verify unchanged historical source bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = ROOT/"artifact_integrity.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_checks():
    results = {}
    for label,folder,manifest in (
        ("original_package",REPO/"SchedResearch_reassessment_evidence_20260907","sha256.json"),
        ("r12",ROOT.parent/"r12","artifact_integrity.json"),
        ("intake_history",ROOT/"history","manifest.json")):
        data = json.loads((folder/manifest).read_text(encoding="utf-8"))
        entries = data if label=="original_package" else data["files"]
        failures = []
        for name,item in entries.items():
            expected = item if isinstance(item,str) else item["sha256"]
            if not (folder/name).is_file() or sha(folder/name)!=expected:
                failures.append(name)
        results[label] = {"files":len(entries),"passed":not failures,"failures":failures,
            "manifest_sha256":sha(folder/manifest)}
    if any(not v["passed"] for v in results.values()):
        raise RuntimeError(json.dumps(results))
    return results


def paths():
    selected = {p for p in ROOT.iterdir() if p.is_file() and p!=OUTPUT and p.stat().st_size <= 200_000}
    for folder in ("artifacts","history","figures"):
        selected.update(p for p in (ROOT/folder).rglob("*") if p.is_file() and p.stat().st_size <= 200_000 and "__pycache__" not in p.parts)
    selected.update((ROOT/"inputs_micro").glob("*/*.yaml"))
    return sorted(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    args = parser.parse_args()
    history = historical_checks()
    if args.check:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        failures = [p for p,v in data["files"].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=v["sha256"]]
        current = {p.relative_to(ROOT).as_posix() for p in paths()}
        failures += ["unfrozen:"+p for p in sorted(current-set(data["files"]))]
        if failures:
            raise RuntimeError("R13 snapshot mismatch: "+", ".join(failures))
        print(json.dumps({"r13_files":len(data["files"]),"passed":True,"historical_checks":history}))
        return
    if OUTPUT.exists():
        raise FileExistsError("Preserve the existing freeze; create another named milestone for later work")
    result = {"schema":"r13.artifact-integrity.v1","scope":"compact code/contracts/inputs/evidence/figures; excludes pipeline caches, local replays and dependency environments",
        "historical_checks":history,"files":{p.relative_to(ROOT).as_posix():{"bytes":p.stat().st_size,"sha256":sha(p)} for p in paths()}}
    with OUTPUT.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(result,f,indent=2); f.write("\n")
    print(json.dumps({"snapshot":str(OUTPUT),"files":len(result["files"]),"bytes":sum(v["bytes"] for v in result["files"].values()),"historical_checks":history}))


if __name__ == "__main__":
    main()
