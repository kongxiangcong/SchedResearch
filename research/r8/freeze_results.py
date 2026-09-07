"""One-time manifest of the explicit completed R8 artifact set, allowing future additions."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "r8"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    destination = R8 / "artifact_integrity.json"
    assert not destination.exists(), "do not rewrite a completed round manifest"
    lineage = json.loads((R8 / "history_lineage.json").read_text(encoding="utf8"))
    successor = ROOT / lineage["successor_progress"]["snapshot"]
    assert sha(ROOT / "research_progress.md") == sha(successor) == lineage["successor_progress"]["sha256"]
    require_names = ["experiment_report.md", "redteam_report.md", "redteam_results.json", "check_results.py"]
    assert all((R8 / name).is_file() for name in require_names)
    # This is a snapshot whitelist, not an equality check on all future directory contents.
    paths = sorted(p for p in R8.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    hashes["research_progress.md"] = sha(successor)
    manifest = {"schema": "r8.explicit-artifact-set.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_level": "source accounting, CPU fixtures and single-payload finite order checks; no target performance",
                "sha256": hashes, "snapshot_overrides": {"research_progress.md": successor.relative_to(ROOT).as_posix()},
                "future_rule": "Only these named files are frozen. Future R8 additions are permitted; root may append rows under new lineage preserving this successor. Do not rewrite this manifest or R1-R7."}
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(json.dumps({"status": "PASS", "listed_artifacts": len(hashes)}))


if __name__ == "__main__":
    main()
