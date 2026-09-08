"""Record task-local dependency identity and capabilities without reading secrets."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def command(args: list[str], cwd: Path = ROOT) -> dict:
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": args, "error": type(exc).__name__}
    data = p.stdout + p.stderr
    encoding = "utf-16-le" if args[0] == "wsl" and b"\x00" in data else "utf-8"
    return {"command": args, "returncode": p.returncode, "output": data.decode(encoding, errors="replace").strip()}


def main() -> None:
    spec = json.loads((ROOT / "dependencies.json").read_text())
    dependencies = []
    for repo in spec["repositories"]:
        dest = ROOT / "deps" / repo["name"]
        dependencies.append({**repo, "head": command(["git", "rev-parse", "HEAD"], dest),
                             "status": command(["git", "status", "--porcelain"], dest)})
    result = {"schema": "r12.environment.v1", "generated_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "python": sys.version, "executable": sys.executable,
              "dependencies": dependencies,
              "packages": {name: version(name) for name in ("stream-dse", "zigzag-dse", "ortools", "numpy", "xdsl", "pydantic")},
              "requirements_lock_sha256": hashlib.sha256((ROOT / "requirements.lock.txt").read_bytes()).hexdigest(),
              "tool_paths": {name: shutil.which(name) for name in ("uv", "git", "cmake", "ninja", "g++", "clang++", "wsl", "docker")},
              "wsl_version": command(["wsl", "--version"]), "wsl_distributions": command(["wsl", "--list", "--verbose"]),
              "hardware": {"board": None, "firmware": None, "harvest_mask": None, "device_performance_qualified": False},
              "git_branch": command(["git", "branch", "--show-current"]),
              "tracked_diff": command(["git", "diff", "--name-only"])}
    result["pinned_sources_valid"] = all(
        dep["head"].get("returncode") == 0 and dep["head"]["output"] == dep["commit"]
        and dep["status"].get("returncode") == 0 and not dep["status"]["output"]
        for dep in dependencies
    )
    path = ROOT / "artifacts" / "environment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    if not result["pinned_sources_valid"]:
        raise SystemExit("A fixed dependency has drifted or is dirty; see environment.json")


if __name__ == "__main__":
    main()
