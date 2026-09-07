"""Freeze bounded primary-source inputs for R6; never modifies R1-R5."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
QWEN = "f62dc9bf2c90353b442a56e74391fbb8c689b55e"
GEMMINI = "8c3f9923a44a2fe2c7930587be297d6d4f8c09ca"
ARM = "79d0fccfe59cab7fd0cab97c65050d2824c5269f"
RIALLTO = "74a26aade2c2762e2854d5ab78f01d180eaeaead"
XRT = "42cba83aee86b253c49eccd484646e91d062468d"

ITEMS = [
    ("qwen/cache_utils.py", f"https://raw.githubusercontent.com/huggingface/transformers/{QWEN}/src/transformers/cache_utils.py"),
    ("qwen/generation_utils.py", f"https://raw.githubusercontent.com/huggingface/transformers/{QWEN}/src/transformers/generation/utils.py"),
    ("qwen/config.json", "https://huggingface.co/Qwen/Qwen3.5-4B/resolve/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json"),
    ("qwen/modeling_qwen3_5.py", f"https://raw.githubusercontent.com/huggingface/transformers/{QWEN}/src/transformers/models/qwen3_5/modeling_qwen3_5.py"),
    ("gemmini/tree.json", f"https://api.github.com/repos/ucb-bar/gemmini/git/trees/{GEMMINI}?recursive=1"),
    ("riallto/tree.json", f"https://api.github.com/repos/AMDResearch/Riallto/git/trees/{RIALLTO}?recursive=1"),
    ("riallto/README.md", f"https://raw.githubusercontent.com/AMDResearch/Riallto/{RIALLTO}/README.md"),
    ("arm/tree.json", f"https://api.github.com/repos/ARM-software/CMSIS-Ethos-U/git/trees/{ARM}?recursive=1"),
    ("riallto/faq.html", "https://riallto.ai/faq.html"),
]
ITEMS += [("gemmini/" + name, f"https://raw.githubusercontent.com/ucb-bar/gemmini/{GEMMINI}/src/main/scala/gemmini/{name}")
          for name in ["CounterFile.scala", "ConfigsFP.scala", "ExecuteController.scala", "XactTracker.scala"]]
ITEMS += [("riallto/" + name, f"https://raw.githubusercontent.com/AMDResearch/Riallto/{RIALLTO}/npu/runtime/{name}")
          for name in ["apprunner.py", "aie_host_utils.py", "kernelinstance.py"]]
ITEMS += [("arm/ethosu_pmu.h", f"https://raw.githubusercontent.com/ARM-software/CMSIS-Ethos-U/{ARM}/source/include/ethosu_pmu.h")]
ITEMS += [("xrt/" + name, f"https://raw.githubusercontent.com/Xilinx/XRT/{XRT}/src/runtime_src/core/tools/common/tests/{name}")
          for name in ["TestDF_bandwidth.cpp", "TestDF_bandwidth.h", "TestVerify.cpp", "TestVerify.h", "TestIPU.cpp"]]
ITEMS += [
    ("xrt/SubCmdValidate.cpp", f"https://raw.githubusercontent.com/Xilinx/XRT/{XRT}/src/runtime_src/core/tools/xbutil2/SubCmdValidate.cpp"),
    ("xrt/TestRunner.cpp", f"https://raw.githubusercontent.com/Xilinx/XRT/{XRT}/src/runtime_src/core/tools/common/TestRunner.cpp"),
    ("xrt/device_windows.cpp", f"https://raw.githubusercontent.com/Xilinx/XRT/{XRT}/src/runtime_src/core/pcie/windows/device_windows.cpp"),
]


def fetch(item):
    name, url = item
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"path": name, "url": url}
    try:
        with urlopen(Request(url, headers={"User-Agent": "R6-primary-source-audit"}), timeout=30) as response:
            data = response.read(8_000_001)
            if len(data) > 8_000_000:
                raise ValueError("source exceeds bounded 8 MB download")
            row["resolved_url"] = response.url
        path.write_bytes(data)
        row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), access="download")
    except Exception as exc:
        row.update(access="failed", error=f"{type(exc).__name__}: {exc}")
    return row


def main():
    rows = list(ThreadPoolExecutor(max_workers=4).map(fetch, ITEMS))
    inherited = [
        ("r4/sources/qwen/config.json", "ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670"),
        ("r4/sources/qwen/modeling_qwen3_5.py", "458360c8072e6130580639170ad3e645b975512dbabae31eab5f92de5f0f09ef"),
        ("r5/sources/gemmini/README.md", "9c5977d88b6ffa0fb04e5a8f878eb984d2f4c8c329539b6c8b29b57f2d2c42b7"),
        ("r5/sources/gemmini/src/main/scala/gemmini/DMA.scala", "db6d9d61f8794f6d60508c5844a2b287ffab0cd795a662b84b970dd9615e5dc1"),
        ("r5/sources/gemmini/src/main/scala/gemmini/Configs.scala", "178c21ac741c89c08158efa71fb34da35d27b75bd50bde5116a5e19178f8391b"),
        ("r5/sources/gemmini/src/main/scala/gemmini/Scratchpad.scala", "e4d3a12c700fe9edaf5c2ce2f283ec5233a98bd103fb04054160e8097cb89a4f"),
        ("r5/sources/arm/cmsis_source_README.md", "9a77c718d17f8fcf5a77c6df825a2be1712aab14e054cca093223586205fb035"),
        ("r5/sources/arm/ethos_u85_trm_102685_0000_05_en.pdf", "3fc6287d861b482e12f29ecd02103128fece6a78ffbe4656332ebb08aaffb8ca"),
    ]
    inherited_rows = []
    for name, expected in inherited:
        data = (ROOT.parents[1] / name).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        inherited_rows.append(dict(path=name, expected_sha256=expected, sha256=actual, matches=actual == expected))
        assert actual == expected, name
    local = Path("C:/Windows/System32/AMD/DPU_Sequence/df_bw_dpu.txt")
    if local.exists():
        data = local.read_bytes()
        destination = ROOT / "xrt/installed_df_bw_dpu.txt"
        destination.write_bytes(data)
        rows.append(dict(path="xrt/installed_df_bw_dpu.txt", local_source=str(local),
                         bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), access="local_driver_copy"))
    manifest = {"captured_utc": datetime.now(timezone.utc).isoformat(),
                "purpose": "R6 bounded source verification, no device or RTL execution", "files": rows,
                "inherited_files_verified_without_modification": inherited_rows}
    (ROOT / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"downloaded": sum(r["access"] == "download" for r in rows),
                      "failures": [r for r in rows if r["access"] == "failed"]}, indent=2))


if __name__ == "__main__":
    main()
