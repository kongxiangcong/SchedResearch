"""Fetch fixed official archives on Windows; emit hashes and a local CPM cache.

No upstream file is edited. Boost dependency traversal follows its CMake target names.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/npe_downloads"
OUT.mkdir(parents=True, exist_ok=True)
entries = json.loads((ROOT / "npe_source_archives.json").read_text())
seen = {e["name"] for e in entries}


def fetch(entry: dict) -> tuple[dict, set[str]]:
    path = OUT / (entry["name"] + ".tar.gz")
    if not path.exists():
        request = urllib.request.Request(entry["url"], headers={"User-Agent": "SchedResearch-R12"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        path.write_bytes(data)
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != entry["sha256"]:
        raise RuntimeError(f"Archive SHA256 differs from frozen lock: {entry['name']}")
    entry = dict(entry, sha256=observed, bytes=path.stat().st_size)
    entry["archive"] = "artifacts/npe_downloads/" + path.name
    deps = set()
    with tarfile.open(path) as archive:
        top = archive.getmembers()[0].name.split("/")[0]
        entry["root_directory"] = top
        if entry["name"].startswith("boost_"):
            cmake = archive.extractfile(top + "/CMakeLists.txt").read().decode()
            deps = set(re.findall(r"Boost::([a-z0-9_]+)", cmake))
    print(json.dumps({"name": entry["name"], "bytes": entry["bytes"], "sha256": entry["sha256"]}), flush=True)
    return entry, deps


pending = entries
done = []
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    while pending:
        results = list(pool.map(fetch, pending))
        pending = []
        for entry, deps in results:
            done.append(entry)
            for dep in sorted(deps):
                key = "boost_" + dep
                if key not in seen:
                    raise RuntimeError(f"Boost dependency missing from frozen archive lock: {key}")
(OUT / "manifest.json").write_text(json.dumps(sorted(done, key=lambda e: e["name"]), indent=2) + "\n")
