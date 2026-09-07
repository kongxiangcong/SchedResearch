"""Audit saved experiment artifacts independently of simulation execution."""
import csv
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "experiments" / "results" / "r3"
    manifest = json.loads((directory / "manifest.json").read_text())
    for path, expected in manifest["sources_sha256"].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected, path
    rows = list(csv.DictReader((directory / "samples.csv").open(newline="", encoding="utf-8")))
    assert len(rows) == manifest["test_samples"]
    groups = {}
    for row in rows:
        groups.setdefault((row["config"], row["seed"]), []).append(row)
    for group in groups.values():
        assert {x["policy"] for x in group} == {"A", "A2", "B", "C"}
        assert len({x["duration_sha256"] for x in group}) == 1
    metrics = [json.loads(line) for line in (directory / "metrics.jsonl").read_text().splitlines()]
    assert len(metrics) == len(rows)
    for row in metrics:
        m = row["metrics"]
        assert m["decision_count"] == int(row["tasks"])
        assert m["wakeup_messages"] == m["dependency_edges"]
        assert all(-1e-9 <= x <= 1 + 1e-9 for x in m["resource_reserved_utilization"].values())
        assert m["abstract_state_bits"] == sum(m["abstract_state_breakdown"].values())
        assert all(v >= -1e-8 for k, v in m.items() if k.endswith("_wait_task_cycles"))
    traces = 0
    for cfg_file in (directory / "contracts").glob("*.json"):
        cfg = json.loads(cfg_file.read_text())
        by_id = {x["task_id"]: x for x in cfg["descriptors"]}
        for policy in ("A", "A2", "B", "C"):
            entries = json.loads((directory / "traces" / (cfg_file.stem + "_" + policy + ".json")).read_text())
            trace = {e["task"]: e for e in entries}
            assert len(entries) == len(by_id) and set(trace) == set(by_id)
            for tid, desc in by_id.items():
                assert abs(trace[tid]["service"] - cfg["durations"][tid]) < 1e-8
                for dep in desc["wait"]:
                    assert trace[tid]["dispatch"] + 1e-8 >= trace[dep["event"]]["finish"]
            for resource in {r for x in entries for r in x["resources"]}:
                intervals = sorted((e["dispatch"], e["finish"]) for e in entries if resource in e["resources"])
                assert all(b[0] + 1e-8 >= a[1] for a, b in zip(intervals, intervals[1:]))
            traces += 1
    result = {"source_hashes_verified": len(manifest["sources_sha256"]), "paired_seed_groups": len(groups),
              "sample_rows": len(rows), "metrics_rows": len(metrics), "saved_traces_replayed": traces,
              "status": "PASS", "scope": "artifact consistency, common samples, safety, bounds; not hardware calibration"}
    (directory / "artifact_check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
