"""Verify official source archives and prepare Linux-local CPM overrides."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent
manifest_path = root / "artifacts/npe_downloads/manifest.json"
manifest = json.loads(manifest_path.read_text())
destination = Path("/opt/schedresearch-r12/download_sources")
destination.mkdir(parents=True, exist_ok=True)
cache_lines = ["# Fixed official archives, SHA256 verified before extraction."]
for entry in manifest:
    archive = root / entry["archive"]
    observed = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert observed == entry["sha256"], entry["name"]
    package_root = destination / entry["name"]
    marker = package_root / ".archive-sha256"
    if package_root.exists():
        assert marker.read_text().strip() == observed, str(package_root)
    else:
        package_root.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(package_root, filter="data")
        marker.write_text(observed + "\n")
    source_dir = package_root / entry["root_directory"]
    assert source_dir.is_dir()
    variable = ("FETCHCONTENT_SOURCE_DIR_PYBIND11" if entry["name"] == "pybind11"
                else "CPM_" + entry["name"] + "_SOURCE")
    cache_lines.append(f'set({variable} "{source_dir}" CACHE PATH "Fixed official source archive" FORCE)')
    print(json.dumps({"name": entry["name"], "source": str(source_dir), "sha256": observed}))
cache = destination / "sources.cmake"
cache.write_text("\n".join(cache_lines) + "\n")
print(str(cache))
