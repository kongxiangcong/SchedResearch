"""Run the current R12 offline qualification, preserving historical results."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="Also rerun the real upstream analytical TETRA smoke")
    args = parser.parse_args()
    scripts = ["workload_intake.py", "qualification.py", "independent_checks.py", "environment_probe.py"]
    if args.baseline:
        scripts.append("baseline_smoke.py")
    logdir = ROOT / "artifacts" / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    for script in scripts:
        with (logdir / (script + ".log")).open("w", encoding="utf-8") as logfile:
            p = subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / script)], cwd=ROOT,
                               stdout=logfile, stderr=subprocess.STDOUT)
        print(f"{script}: {'PASS' if p.returncode == 0 else 'FAIL'}", flush=True)
        if p.returncode:
            raise SystemExit(p.returncode)
    print("Offline scope complete. Native G0 and H1/H2 performance remain unqualified.")


if __name__ == "__main__":
    main()
