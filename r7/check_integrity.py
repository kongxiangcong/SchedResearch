"""Verify R7 and explicit R6/R5 progress snapshots without editing old evidence.

Before the final R7 table edit: --verify-history.
After the final R7 table edit: --record-successor (once), then --freeze-r7 (once).
Thereafter: run with no arguments. Stdout is a receipt, not a performance gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "r7"
MANIFEST = ROUND / "artifact_integrity.json"
LINEAGE = ROUND / "history_lineage.json"
EXCLUDED_CACHE_ROOTS = (
    "r7/sources/kernel_access/riallto_repo",
    "r7/sources/kernel_access/ryzenai_repo",
    "r7/sources/kernel_access/dynamicdispatch_repo",
)


def require(condition: bool, message: object) -> None:
    if not condition:
        raise RuntimeError(str(message))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_new_json(path: Path, value: dict) -> None:
    # Exclusive creation makes --freeze-r7 refuse replacement even during a race.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def rows(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.startswith("| R") and not line.startswith("| Round |")]


def verify_rows(parent_path: Path, successor_path: Path) -> int:
    parent, successor = rows(parent_path), rows(successor_path)
    require(parent, f"No historical table rows: {parent_path}")
    for line in parent_path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("| Round |"):
            require(line in successor_path.read_text(encoding="utf-8-sig").splitlines(),
                    "Historical eight-field table header changed")
    parent_counts, successor_counts = Counter(parent), Counter(successor)
    for row, count in parent_counts.items():
        require(successor_counts[row] == count, {"historical_row_changed_removed_or_duplicated": row})
    position = 0
    for row in parent:
        while position < len(successor) and successor[position] != row:
            position += 1
        require(position < len(successor), "Historical table row order changed")
        position += 1
    return len(parent)


def verify_mapping(label: str, mapping: dict[str, str], progress: str | None) -> int:
    errors = []
    for logical, expected in mapping.items():
        physical = progress if logical == "research_progress.md" and progress else logical
        path = ROOT / physical
        if not path.is_file():
            errors.append({"logical": logical, "physical": physical, "error": "missing"})
        elif digest(path) != expected:
            errors.append({"logical": logical, "physical": physical, "error": "changed"})
    require(not errors, {"parent": label, "integrity_errors": errors})
    return len(mapping)


def verify_history(require_successor: bool = False) -> dict:
    lineage = read_json(LINEAGE)
    require(lineage["schema_version"] == "r7.history-lineage.v1", "Unexpected lineage schema")
    for parent in lineage["parent_manifests"]:
        require(digest(ROOT / parent["path"]) == parent["sha256"], {"parent_manifest_changed": parent["path"]})

    old6 = read_json(ROOT / "r6/artifact_integrity.json")["sha256"]
    old5 = read_json(ROOT / "r5/artifact_integrity.json")["sha256"]
    old4 = read_json(ROOT / "experiments/results/r4/artifact_integrity.json")["artifact_sha256"]
    old_lineage = read_json(ROOT / "r6/history_lineage.json")
    r6_snapshot = lineage["r6_progress_snapshot"]
    r5_snapshot = old_lineage["r5_progress_snapshot"]
    require(r6_snapshot["logical_path"] == "research_progress.md", "Invalid R6 logical mapping")
    require(r6_snapshot["sha256"] == old6["research_progress.md"] == old_lineage["successor_progress"]["sha256"],
            "R6 snapshot hash must equal both original R6 authorities")
    require(digest(ROOT / r6_snapshot["path"]) == r6_snapshot["sha256"], "R6 progress snapshot changed")
    require(r5_snapshot["sha256"] == old5["research_progress.md"] == old_lineage["successor_progress"]["parent_sha256"],
            "R5 mapping must retain original R6 lineage")
    require(lineage["r5_progress_snapshot"] == r5_snapshot, "R7 must reuse exact R5 snapshot mapping")
    for old_parent in old_lineage["parent_manifests"]:
        require(digest(ROOT / old_parent["path"]) == old_parent["sha256"], "R6 parent lineage changed")

    count6 = verify_mapping("R6", old6, r6_snapshot["path"])
    count5 = verify_mapping("R5", old5, r5_snapshot["path"])
    count4 = verify_mapping("R4", old4, None)
    require((count6, count5, count4) == (89, 262, 612), "Unexpected frozen parent coverage")
    # Verify that the complete R6 file scope did not gain unmanifested files.
    current6 = {p.relative_to(ROOT).as_posix() for p in (ROOT / "r6").rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
                and p.name != "artifact_integrity.json"}
    current6.add("research_progress.md")
    require(current6 == set(old6), {"r6_scope_new": sorted(current6 - set(old6)),
                                  "r6_scope_missing": sorted(set(old6) - current6)})

    root_progress = ROOT / "research_progress.md"
    historical_rows = verify_rows(ROOT / r6_snapshot["path"], root_progress)
    verify_rows(ROOT / r5_snapshot["path"], ROOT / r6_snapshot["path"])
    successor = lineage["successor_progress"]
    require(successor["parent_sha256"] == r6_snapshot["sha256"], "Successor has wrong parent")
    require(successor["path"] == "research_progress.md", "Unexpected successor progress path")
    if successor["sha256"] is not None:
        require(digest(root_progress) == successor["sha256"], "Recorded R7 successor progress changed")
        require(successor["sha256"] != r6_snapshot["sha256"], "R7 successor must differ from R6")
        require(any(row.startswith("| R7") for row in rows(root_progress)), "No R7 table row")
    elif require_successor:
        raise RuntimeError("R7 successor not recorded; complete root table, then --record-successor")

    return {"r6_logical_paths_via_explicit_snapshot": count6,
            "r5_logical_paths_via_r6_snapshot": count5, "r4_original_paths": count4,
            "historical_table_rows_preserved_in_order": historical_rows,
            "successor_status": "recorded" if successor["sha256"] is not None else "pending_not_performance_accepted"}


def round_paths() -> list[Path]:
    excluded = {(ROOT / item).resolve() for item in EXCLUDED_CACHE_ROOTS}
    result = []
    for directory, names, files in os.walk(ROUND):
        current = Path(directory)
        names[:] = sorted(name for name in names if name not in {"__pycache__", ".git"}
                          and (current / name).resolve() not in excluded)
        for name in files:
            path = current / name
            if path.suffix != ".pyc" and path != MANIFEST:
                result.append(path)
    result.append(ROOT / "research_progress.md")
    return sorted(result)


def record_successor() -> dict:
    require(not MANIFEST.exists(), "R7 is frozen; cannot modify its lineage")
    parents = verify_history()
    lineage = read_json(LINEAGE)
    require(lineage["successor_progress"]["sha256"] is None,
            "Successor already recorded; do not overwrite lineage, record a new explicit amendment")
    current_hash = digest(ROOT / "research_progress.md")
    require(current_hash != lineage["r6_progress_snapshot"]["sha256"], "R7 table has not been appended")
    require(any(row.startswith("| R7") for row in rows(ROOT / "research_progress.md")), "No R7 table row")
    lineage["successor_progress"]["sha256"] = current_hash
    lineage["successor_progress"]["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    lineage["successor_progress"]["status"] = "RECORDED"
    LINEAGE.write_text(json.dumps(lineage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "PASS", "operation": "record-successor", "successor_sha256": current_hash,
            **parents, "successor_status": "recorded"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verify-history", action="store_true")
    group.add_argument("--record-successor", action="store_true")
    group.add_argument("--freeze-r7", action="store_true")
    args = parser.parse_args()
    if args.record_successor:
        result = record_successor()
    elif args.verify_history:
        result = {"status": "PASS", "operation": "verify-history", **verify_history()}
    else:
        if args.freeze_r7:
            require(not MANIFEST.exists(), "Refusing to overwrite frozen R7 manifest; record a successor instead")
        else:
            require(MANIFEST.exists(), "R7 not frozen yet; use --verify-history during development")
        parents = verify_history(require_successor=True)
        actual = {p.relative_to(ROOT).as_posix(): digest(p) for p in round_paths()}
        if args.freeze_r7:
            write_new_json(MANIFEST, {
                "status": "FROZEN", "schema_version": "r7.artifact-integrity.v1",
                "scope": "R7 explicit artifacts and successor progress; no performance-gate acceptance",
                "exclusions": {"retrieval_cache_roots": EXCLUDED_CACHE_ROOTS,
                               "directory_names": [".git", "__pycache__"], "file_suffixes": [".pyc"]},
                "parent_verification": parents, "sha256": actual})
        else:
            expected = read_json(MANIFEST)["sha256"]
            require(actual == expected, {"missing": sorted(set(expected) - set(actual)),
                                         "new": sorted(set(actual) - set(expected)),
                                         "changed": [p for p in actual if p in expected and actual[p] != expected[p]]})
        result = {"status": "PASS", "operation": "freeze-r7" if args.freeze_r7 else "verify",
                  "r7_and_successor_progress_paths": len(actual), **parents}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, KeyError, ValueError) as error:
        raise SystemExit(f"FAIL: {error}") from error
