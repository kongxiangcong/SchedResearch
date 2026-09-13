"""Locate the SchedResearch workspace and frozen upstream contracts.

Everything in this package resolves paths from the repository root so that the
new infrastructure directory can be moved without breaking references to the
frozen R1-R13 material.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def repo_root(start: Path | None = None) -> Path:
    """Walk up from *start* until the known repository marker is found."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "research" / "r13" / "numerical_contract.json").is_file():
            return candidate
        if (candidate / "research" / "research_progress.md").is_file():
            return candidate
    raise RuntimeError(f"Could not locate SchedResearch root above {here}")


ROOT = repo_root()
INFRA_DIR = ROOT / "research" / "infra_open_source"
VENDOR_DIR = INFRA_DIR / "vendor"
RUNS_DIR = INFRA_DIR / "runs"
R13_DIR = ROOT / "research" / "r13"
NUMERICAL_CONTRACT = R13_DIR / "numerical_contract.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def sha256_json(obj: object) -> str:
    """Stable hash of a JSON-serialisable object.

    Keys are sorted and separators fixed so that the same logical content
    always hashes identically, which is what makes plan identity reproducible.
    """
    import json

    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(text.encode("utf-8"))


def relative(path: Path | str) -> str:
    """Repository-relative POSIX path, for evidence files that must travel."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


def ensure_dir(path: Path | str) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def check_paths_exist(paths: Iterable[Path | str]) -> list[str]:
    return [str(p) for p in paths if not Path(p).exists()]
