"""Fetch pinned sources without changing existing checkouts; install locally only."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"{args!r}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def fetch(name: str) -> None:
    manifest = json.loads((ROOT / "dependencies.json").read_text())
    spec = next(s for s in manifest["repositories"] if s["name"] == name)
    dest = ROOT / "deps" / name
    if not dest.exists():
        dest.mkdir(parents=True)
        run("git", "init", "--quiet", str(dest))
        run("git", "remote", "add", "origin", spec["url"], cwd=dest)
    if run("git", "remote", "get-url", "origin", cwd=dest) != spec["url"]:
        raise RuntimeError(f"Unexpected origin at {dest}")
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=dest, capture_output=True, text=True)
    if head.returncode == 0:
        if head.stdout.strip() != spec["commit"] or run("git", "status", "--porcelain", cwd=dest):
            raise RuntimeError(f"Preserving existing mismatched or dirty checkout: {dest}")
    else:
        if run("git", "ls-files", "--others", "--exclude-standard", cwd=dest):
            raise RuntimeError(f"Preserving existing untracked files: {dest}")
        run("git", "fetch", "--depth", "1", "origin", spec["commit"], cwd=dest)
        run("git", "checkout", "--detach", spec["commit"], cwd=dest)
    actual = run("git", "rev-parse", "HEAD", cwd=dest)
    if actual != spec["commit"]:
        raise RuntimeError(f"Revision mismatch: {name}")
    print(json.dumps({"repository": name, "commit": actual, "status": "verified"}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", choices=["tt-isa-documentation", "stream", "tt-npe"])
    args = parser.parse_args()
    if args.fetch:
        fetch(args.fetch)
    else:
        parser.error("Choose --fetch REPOSITORY; Python setup commands are in README.md")


if __name__ == "__main__":
    main()
