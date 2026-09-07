"""Freeze primary-source resource evidence; does not touch prior rounds or weights."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import urllib.request
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MANIFEST = OUT / "resource_source_manifest.json"
rows: list[dict] = []
prior = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
failures: list[dict] = prior.get("failures", [])
prior_files = {row["path"]: row for row in prior.get("files", [])}


def save(relative: str, data: bytes, **metadata: object) -> None:
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    rows.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), **metadata})


def fetch(url: str, relative: str) -> bytes | None:
    target = OUT / relative
    if target.exists():
        data = target.read_bytes()
        previous = prior_files.get(relative, {})
        metadata = {key: value for key, value in previous.items() if key not in {"path", "bytes", "sha256"}}
        if not metadata:
            metadata = {"requested_url": url, "access": "existing_frozen_file"}
        save(relative, data, **metadata)
        return data
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SchedResearch-R5-primary-source-audit"})
        with urllib.request.urlopen(request, timeout=45) as response:
            data = response.read()
            save(relative, data, url=url, resolved_url=response.url, access="download")
            return data
    except Exception as exc:
        failures.append({"url": url, "path": relative, "error": f"{type(exc).__name__}: {exc}"})
        return None


def main() -> None:
    inherited = [
        ("r4/sources/qwen/config.json", "qwen/config.json"),
        ("r4/sources/qwen/modeling_qwen3_5.py", "qwen/modeling_qwen3_5.py"),
        ("r4/sources/qwen/representative_weight_shapes.json", "qwen/representative_weight_shapes.json"),
        ("r4/sources/qwen/manifest.json", "qwen/r4_manifest.json"),
        ("r4/sources/flux/FLUX.2-klein-4B/transformer/config.json", "flux/config.json"),
        ("r4/sources/flux/black-forest-labs__flux2/src/flux2/model.py", "flux/model.py"),
        ("r4/sources/flux/source_manifest.json", "flux/r4_manifest.json"),
        ("r4/sources/flux/ARM-software__CMSIS-Ethos-U/source/README.md", "arm/cmsis_source_README.md"),
        ("r4/sources/flux/ARM-software__CMSIS-Ethos-U/git_revision.json", "arm/git_revision.json"),
    ]
    for original, relative in inherited:
        save(relative, (ROOT / original).read_bytes(), inherited_from=original, access="verified_copy")
    api = fetch("https://api.github.com/repos/ucb-bar/gemmini/commits/HEAD", "gemmini/commit.json")
    if not api:
        try:
            result = subprocess.run(["git", "ls-remote", "https://github.com/ucb-bar/gemmini.git", "HEAD"], capture_output=True, text=True, check=True, timeout=45)
            api = json.dumps({"sha": result.stdout.split()[0], "method": "git ls-remote HEAD fallback after API rate limit"}).encode("utf-8")
            save("gemmini/commit.json", api, access="git_ls_remote")
        except Exception as exc:
            failures.append({"path": "gemmini/commit.json", "error": f"git fallback {type(exc).__name__}: {exc}"})
    if api:
        revision = json.loads(api)["sha"]
        for filename in ["README.md", "src/main/scala/gemmini/Scratchpad.scala", "src/main/scala/gemmini/DMA.scala", "src/main/scala/gemmini/Configs.scala"]:
            fetch(f"https://raw.githubusercontent.com/ucb-bar/gemmini/{revision}/{filename}", f"gemmini/{filename}")
    pdf = fetch("https://documentation-service.arm.com/static/67b5ba01ce2747241fce860f", "arm/ethos_u85_trm_102685_0000_05_en.pdf")
    if pdf:
        try:
            import fitz
            document = fitz.open(stream=pdf, filetype="pdf")
            extracted = "\n\n".join(f"[PDF page {i + 1}]\n" + page.get_text() for i, page in enumerate(document))
            save("arm/ethos_u85_trm_102685_0000_05_en.txt", extracted.encode("utf-8"), access="pymupdf_text_extraction")
        except Exception as exc:
            failures.append({"path": "arm/ethos_u85_trm_102685_0000_05_en.txt", "error": f"{type(exc).__name__}: {exc}"})
    # Browser parser searches failed; recorded rather than silently interpreted as absence.
    failures.extend([
        {"tool": "web.find", "url": "https://documentation-service.arm.com/static/67b5ba01ce2747241fce860f", "pattern": pattern, "error": "No matching text found / Internal Error; local PDF text extraction is the fallback evidence"}
        for pattern in ["ext_rd_stall_limit", "NoC", "arbitration", "outstanding", "stall", "bank"]
    ])
    unique_failures = list({json.dumps(row, sort_keys=True): row for row in failures}.values())
    MANIFEST.write_text(json.dumps({"captured_utc": prior.get("captured_utc", datetime.now(timezone.utc).isoformat()), "verified_utc": datetime.now(timezone.utc).isoformat(), "weight_payloads_downloaded": False, "files": rows, "failures": unique_failures}, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(rows), "failures": len(unique_failures), "manifest": str(MANIFEST)}, indent=2))


if __name__ == "__main__":
    main()
