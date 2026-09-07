"""Read-only R9 named artifact / lineage verification, future additions allowed."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    handoff = json.loads((ROOT / "r9/handoff_integrity.json").read_text(encoding="utf8"))
    for path, expected in handoff["handoff_files"].items():
        assert sha(ROOT / path) == expected, path
    manifest = json.loads((ROOT / "r9/results_manifest.json").read_text(encoding="utf8"))
    for path, expected in manifest["files"].items():
        assert sha(ROOT / path) == expected, path
    lineage = json.loads((ROOT / "r9/history_lineage.json").read_text(encoding="utf8"))
    parent = ROOT / lineage["parent_snapshot"]
    successor = ROOT / lineage["successor_snapshot"]
    assert sha(parent) == lineage["parent_sha256"]
    assert sha(successor) == lineage["successor_sha256"]
    parent_rows = [line for line in parent.read_text(encoding="utf8").splitlines() if line.startswith("| R")]
    successor_rows = [line for line in successor.read_text(encoding="utf8").splitlines() if line.startswith("| R")]
    root_rows = [line for line in (ROOT / "research_progress.md").read_text(encoding="utf8").splitlines() if line.startswith("| R")]
    assert all(line in successor_rows for line in parent_rows), "old parent row rewritten"
    assert all(line in root_rows for line in successor_rows), "R9 successor row missing from current root"
    added = [line for line in successor_rows if line not in parent_rows]
    assert added == lineage["added_rows"]
    for row in added:
        assert row.startswith("| R9：") and len(row.split("|")) == 10, row
    audit = json.loads((ROOT / manifest["audit_result"]).read_text(encoding="utf8"))
    assert audit["status"] == "PASS", audit
    print(json.dumps({"status": "PASS", "named_files": len(manifest["files"]),
                      "handoff_files": len(handoff["handoff_files"]), "historical_rows_preserved": len(parent_rows),
                      "actual_R9_rows": len(added), "scope": "R9 frozen reference-model evidence and lineage, not real-target acceptance"}, ensure_ascii=False))


if __name__ == "__main__":
    check()
