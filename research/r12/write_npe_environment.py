"""Write a bounded, non-secret inventory for the dedicated R12 Linux NPE build."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import xml.etree.ElementTree as ET


def command(args: list[str], cwd: Path | None = None) -> dict:
    try:
        process = subprocess.run(args, cwd=cwd, text=True, encoding="utf-8", capture_output=True, timeout=20)
        return {"exit_code": process.returncode, "stdout": process.stdout.strip(), "stderr": process.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--phase-records", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    source = args.task_root / "tt-npe"
    install = args.task_root / "install/tt-npe"
    phases = []
    if args.phase_records.exists():
        phases = [json.loads(line) for line in args.phase_records.read_text().splitlines() if line.strip()]
    report = {
        "schema": "r12-npe-environment-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "exit_code": args.exit_code,
        "passed": args.exit_code == 0,
        "passed_criteria": "all requested phases including the official CLI; see ready_for_coarse_api_use for library readiness",
        "ready_for_coarse_api_use": all(any(p["phase"] == name and p["exit_code"] == 0 for p in phases) for name in ("build", "install", "example_api")),
        "upstream_tests_passed": all(any(p["phase"] == name and p["exit_code"] == 0 for p in phases) for name in ("cpp_tests", "python_tests")),
        "evidence_level": "compiled official estimator, upstream tests and documented Python API example only",
        "hardware_measurement": False,
        "full_dfg_timing_calibrated": False,
        "distribution": "SchedResearch-R12",
        "platform": platform.platform(),
        "os_release": Path("/etc/os-release").read_text(),
        "expected_commit": args.expected_commit,
        "source": str(source),
        "build": str(args.task_root / "build/tt-npe"),
        "install": str(install),
        "python_venv": str(args.task_root / "venv-npe"),
        "build_configuration": {
            "type": "Release", "compiler": "GCC12", "enable_libcxx": False,
            "generator": "Ninja", "parallel_jobs": 4,
        },
        "phases": phases,
        "official_cli_passed": next((phase["exit_code"] == 0 for phase in phases if phase["phase"] == "example_cli"), None),
        "official_cli_failure_is_recorded_separately": True,
        "commands": {
            "gcc": command(["gcc-12", "--version"]),
            "gxx": command(["g++-12", "--version"]),
            "cmake": command(["cmake", "--version"]),
            "ninja": command(["ninja", "--version"]),
            "python": command([str(args.task_root / "venv-npe/bin/python"), "--version"]),
            "source_head": command(["git", "-C", str(source), "rev-parse", "HEAD"]),
            "source_status": command(["git", "-C", str(source), "status", "--porcelain"]),
        },
        "test_xml": {},
    }
    for label in ("cpp_tests", "python_tests"):
        path = args.artifact_root / "npe" / f"{label}_{args.run_id}.xml"
        if path.exists():
            root = ET.parse(path).getroot()
            suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
            report["test_xml"][label] = {
                "path": str(path),
                "tests": sum(int(suite.get("tests", 0)) for suite in suites),
                "failures": sum(int(suite.get("failures", 0)) for suite in suites),
                "errors": sum(int(suite.get("errors", 0)) for suite in suites),
                "skipped": sum(int(suite.get("skipped", suite.get("disabled", 0))) for suite in suites),
            }
    installed_files = []
    if install.exists():
        for path in sorted(install.rglob("*")):
            if path.is_file() and not path.is_symlink():
                installed_files.append({"path": str(path), "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    report["installed_files"] = installed_files
    dependencies = []
    for dependency_root in (source / ".cpmcache", args.task_root / "build/tt-npe/_deps"):
        if dependency_root.exists():
            for dot_git in sorted(dependency_root.rglob(".git")):
                repository = dot_git.parent
                dependencies.append({"path": str(repository), "commit": command(["git", "-C", str(repository), "rev-parse", "HEAD"])})
    report["dependency_commits"] = dependencies
    archive_paths = list((args.task_root / "build/tt-npe").rglob("*.tar.gz"))
    archive_paths.extend((source / ".cpmcache/cpm").glob("CPM_*.cmake"))
    report["downloaded_archives"] = [
        {"path": str(path), "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(archive_paths) if path.is_file()
    ]
    official_archives = args.artifact_root / "npe_downloads/manifest.json"
    if official_archives.exists():
        report["official_source_archives"] = json.loads(official_archives.read_text())
    example_result = args.artifact_root / "npe" / f"example_api_{args.run_id}.json"
    if example_result.exists():
        report["example_api_result"] = {"path": str(example_result), "result": json.loads(example_result.read_text(encoding="utf-8"))}
    destination = args.artifact_root / "npe_environment.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive = args.artifact_root / "npe" / f"environment_{args.run_id}.json"
    archive.write_text(destination.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(destination)}))


if __name__ == "__main__":
    main()
