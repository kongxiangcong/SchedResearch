"""Read-only verification of R8's explicitly listed artifacts and progress lineage."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "r8"


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, detail):
    if not ok:
        raise RuntimeError(str(detail))


def rows(path):
    return [line for line in path.read_text(encoding="utf8").splitlines() if line.startswith("| R")]


def preserved(parent, child):
    before, after = rows(parent), rows(child)
    ca, cb = Counter(before), Counter(after)
    require(all(cb[line] == count for line, count in ca.items()), "changed/duplicated historical row")
    require([line for line in after if line in ca] == before, "historical row order")


def main():
    manifest = read(R8 / "artifact_integrity.json")
    for logical, digest in manifest["sha256"].items():
        physical = manifest["snapshot_overrides"].get(logical, logical)
        require(sha(ROOT / physical) == digest, {"artifact": logical, "physical": physical})
    line = read(R8 / "history_lineage.json")
    parent, child = ROOT / line["parent_progress"]["snapshot"], ROOT / line["successor_progress"]["snapshot"]
    require(sha(parent) == line["parent_progress"]["sha256"], "parent progress sha")
    require(sha(child) == line["successor_progress"]["sha256"], "child progress sha")
    handoff = read(R8 / "handoff_integrity.json")
    require(sha(parent) == handoff["progress_lineage"]["successor_sha256"], "handoff -> R8 parent")
    require(sha(R8 / "handoff_integrity.json") == line["parent_handoff_sha256"], "handoff unchanged")
    preserved(parent, child)
    preserved(child, ROOT / "research_progress.md")
    added = [r for r in rows(child) if r not in set(rows(parent))]
    require(len(added) == 2 and all(r.startswith("| R8：") for r in added), "two actual R8 rows")
    require(all(len(r.split("|")) == 10 for r in added), "eight fields per R8 row")
    require(added == line["added_rows"], "exact new rows")
    receipt = read(R8 / "results/receipt.json")
    require(receipt["status"] == "PASS", "main experiment pass")
    for path, digest in receipt["inputs_sha256"].items():
        require(sha(ROOT / path) == digest, {"experiment input": path})
    for name, digest in receipt["artifact_sha256"].items():
        require(sha(R8 / "results" / name) == digest, {"experiment output": name})
    review = read(R8 / "redteam_results.json")
    require(review["status"] == "PASS", "independent recheck pass")
    require(review["main_receipt_sha256"] == sha(R8 / "results/receipt.json"), "redteam reviewed this run")
    require(review["independent_checker_sha256"] == sha(R8 / "redteam_check.py"), "independent checker identity")
    contract = read(R8 / "target_contract.json")
    require(not contract["decision"]["mechanism_gate_open"], "mechanism remains closed")
    require(contract["observability"]["new_target_runs"] == contract["observability"]["new_Phoenix_runs"] == 0,
            "no device-run claim")
    print(json.dumps({"status": "PASS", "listed_artifacts": len(manifest["sha256"]),
                      "historical_rows_preserved": len(rows(parent)) - 1, "actual_R8_rows": len(added),
                      "root_is_this_successor": sha(ROOT / "research_progress.md") == sha(child),
                      "scope": "listed R8 structural evidence and lineage; future additions allowed; no target/performance acceptance"}))


if __name__ == "__main__":
    main()
