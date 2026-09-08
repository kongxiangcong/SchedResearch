"""Snapshot this round's reviewable files; never modify frozen historical inputs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "artifact_integrity.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        failures = [name for name, data in saved["files"].items()
                    if not (ROOT / name).is_file() or digest(ROOT / name) != data["sha256"]]
        if failures:
            raise SystemExit("Artifact snapshot mismatch: " + ", ".join(failures))
        print(f"PASS: {len(saved['files'])} round artifacts match snapshot")
        return
    paths = {p for p in ROOT.iterdir() if p.is_file() and p != OUTPUT}
    paths.update((ROOT / "artifacts").glob("*.json"))
    paths.update((ROOT / "artifacts" / "npe_downloads").glob("*.json"))
    paths.update(p for p in (ROOT / "artifacts" / "npe").glob("*")
                 if p.is_file() and p.suffix in (".json", ".xml"))
    for folder in (ROOT / "results").iterdir():
        if folder.is_dir():
            paths.update(folder.glob("*.json"))
    result = {"schema": "r12.artifact-integrity.v1",
              "scope": "round code/docs/config and compact results; dependency repositories and WSL disk excluded",
              "files": {p.relative_to(ROOT).as_posix(): {"sha256": digest(p), "bytes": p.stat().st_size}
                        for p in sorted(paths)}}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Snapshot: {len(paths)} round artifacts")


if __name__ == "__main__":
    main()
