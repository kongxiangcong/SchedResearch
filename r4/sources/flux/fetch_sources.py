"""Freeze small official FLUX.2 source/config evidence; never download weights."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parent
HEADERS = {"User-Agent": "SchedResearch-R4-source-audit", "Accept": "application/json"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        return response.read()

def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entries = []
    refs = {}
    jobs = []
    manifest_path = ROOT / "source_manifest.json"
    pinned = json.loads(manifest_path.read_text(encoding="utf-8"))["revisions"] if manifest_path.exists() else {}
    for name in ("FLUX.2-klein-4B", "FLUX.2-klein-base-4B"):
        repo = "black-forest-labs/" + name
        api_url = "https://huggingface.co/api/models/" + repo + ("/revision/" + pinned[repo] if repo in pinned else "")
        raw = get(api_url)
        meta = json.loads(raw)
        refs[repo] = meta["sha"]
        jobs.append((f"{name}/api_model.json", api_url, raw))
        available = {f["rfilename"] for f in meta["siblings"]}
        for file in ("README.md", "LICENSE.md", "model_index.json", "transformer/config.json", "text_encoder/config.json", "text_encoder/model.safetensors.index.json", "vae/config.json", "scheduler/scheduler_config.json"):
            if file in available:
                jobs.append((f"{name}/{file}", f"https://huggingface.co/{repo}/resolve/{meta['sha']}/{file}", None))
    for repo, files in {
        "black-forest-labs/flux2": ["README.md", "LICENSE.md", "src/flux2/model.py", "src/flux2/util.py", "src/flux2/sampling.py", "src/flux2/text_encoder.py", "src/flux2/autoencoder.py", "scripts/cli.py"],
        "huggingface/diffusers": ["src/diffusers/models/transformers/transformer_flux2.py", "src/diffusers/pipelines/flux2/pipeline_flux2_klein.py"],
        "ARM-software/CMSIS-Ethos-U": ["source/README.md"],
    }.items():
        api_url = "https://api.github.com/repos/" + repo + "/commits/main"
        revision = pinned[repo] if repo in pinned else subprocess.check_output(["git", "ls-remote", "https://github.com/" + repo + ".git", "HEAD"], text=True).split()[0]
        raw = json.dumps({"sha": revision, "method": "git ls-remote HEAD at first capture; frozen thereafter", "repository": "https://github.com/" + repo}).encode()
        refs[repo] = revision
        folder = repo.replace("/", "__")
        jobs.append((folder + "/git_revision.json", "https://github.com/" + repo + ".git", raw))
        jobs.extend((folder + "/" + file, f"https://raw.githubusercontent.com/{repo}/{revision}/{file}", None) for file in files)
    jobs.extend([
        ("hardware/ethos_u85_newsroom.html", "https://newsroom.arm.com/blog/ethos-u85", None),
        ("hardware/ethos_u85_product.html", "https://www.arm.com/products/silicon-ip-cpu/ethos/ethos-u85", None),
    ])
    def one(job):
        path, url, data = job
        try:
            data = data if data is not None else get(url)
            out = ROOT / path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            return {"path": path, "url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "retrieved_utc": stamp}
        except Exception as exc:
            return {"path": path, "url": url, "error": str(exc), "retrieved_utc": stamp}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        entries = list(pool.map(one, jobs))
    manifest = {"retrieved_utc": stamp, "weight_downloads": False, "revisions": refs, "files": entries}
    (ROOT / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"revisions": refs, "files": len(entries), "errors": [x for x in entries if "error" in x]}, indent=2))

if __name__ == "__main__":
    main()
