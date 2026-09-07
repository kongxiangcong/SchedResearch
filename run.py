"""Run historical Python commands with research/ as their working directory."""
from pathlib import Path
import os
import subprocess
import sys


def main():
    workspace = Path(__file__).resolve().parent / "research"
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python run.py <Python options, module or research-relative script>\n"
              "Examples:\n"
              "  python run.py -m unittest discover -s tests -v\n"
              "  python run.py -m r4.run --limit 1 --seeds 2 --search-budget 16\n"
              "  python run.py r11/numerical.py\n"
              "All relative input/output paths resolve under research/.")
        return 0
    env = os.environ.copy()
    # Direct script entries also import sibling packages such as r5 and sim.
    env["PYTHONPATH"] = str(workspace) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.call(
        [sys.executable, "-B", "-X", "utf8", *args], cwd=workspace, env=env
    )


if __name__ == "__main__":
    raise SystemExit(main())
