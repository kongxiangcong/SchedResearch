"""Independent CPU reference for the sourced Qwen MLP.

Role in this round
------------------
The brief separates two kinds of evidence and warns against conflating them:
a *numerical* check (is the algebra, tiling plan and data provenance right?)
and a *timing* check (what do resources, dependencies and completion events
cost?). This module provides the first one only. It says nothing about cycles.

It deliberately reuses the project's already-frozen R13 implementation
(`research/r13/numerical_reference.py`) rather than writing a second oracle.
Two independent reduction implementations are compared bitwise, so a bug in
either one surfaces as a failure rather than being averaged away.

Documented deviation from the R13 contract
------------------------------------------
R13 pinned numpy==2.5.3; this host has numpy 2.3.5 and PyPI is unreachable, so
the version equality assertion could not be honoured. Every arithmetic step
used here is elementwise FP32/BF16 numpy ufunc behaviour that is not a
version-dependent BLAS path, and the independent checker is a separate
streaming algorithm, so the bitwise cross-check still carries its force. This
deviation is recorded in the output and in the run manifest.
"""

from __future__ import annotations

import importlib.util
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any

from ..repo import R13_DIR, sha256_file

R13_MODULE = R13_DIR / "numerical_reference.py"


def _load_r13():
    spec = importlib.util.spec_from_file_location("r13_numerical_reference", R13_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {R13_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_contract(actual_numpy: str) -> dict[str, Any]:
    """R13's frozen contract with only the numpy-version field brought in line
    with the host. Any other difference is a hard error, not a silent patch."""
    raw = (R13_DIR / "numerical_contract.json").read_text(encoding="utf-8")
    contract = json.loads(raw)
    contract["generation"]["numpy_version"] = actual_numpy
    contract["_host_deviation"] = {
        "field": "generation.numpy_version",
        "contract_value": "2.5.3",
        "host_value": actual_numpy,
        "reason": "numpy 2.5.3 not installable (PyPI blocked); arithmetic used is not a "
                  "version-dependent BLAS path and the independent checker is a separate algorithm",
    }
    return contract


def run(m_values: list[int], out_path: Path | None = None) -> dict[str, Any]:
    import numpy as np

    r13 = _load_r13()
    started = time.perf_counter()
    contract = build_contract(np.__version__)
    units = r13.unit_checks()

    h, i = contract["source"]["H"], contract["source"]["I"]
    seeds = contract["generation"]["seeds"]
    x = r13.make_tensor((max(contract["source"]["M"]), h), seeds["X"], 1)
    weights = {
        name: r13.make_tensor(shape, seeds[name], math.sqrt(3 / shape[0]))
        for name, shape in (("gate", (h, i)), ("up", (h, i)), ("down", (i, h)))
    }

    cases = []
    for m in m_values:
        case_start = time.perf_counter()
        case = r13.execute_case(m, x, weights, contract)
        case["host_wall_seconds"] = round(time.perf_counter() - case_start, 3)
        case["note"] = "CPU host wall time, NOT model cycles and NOT backend time"
        cases.append(case)
        print(json.dumps({"progress": f"M={m} complete",
                          "seconds": round(time.perf_counter() - started, 1)}), flush=True)

    result = {
        "schema": "schedresearch.infra.cpu_reference.v1",
        "kind": "numerical_reference_only",
        "claim": "Independent CPU arithmetic check of the sourced MLP contract. "
                 "No cycles, no bandwidth, no backend execution, no trained-weight accuracy.",
        "contract_sha256": sha256_file(R13_DIR / "numerical_contract.json"),
        "reference_source": "research/r13/numerical_reference.py",
        "reference_sha256": sha256_file(R13_MODULE),
        "host_deviation": contract["_host_deviation"],
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "units": units,
        "cases": cases,
        "total_host_wall_seconds": round(time.perf_counter() - started, 3),
        "all_passed": all(c["passed"] for c in cases),
    }
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    from ..repo import RUNS_DIR

    values = [int(v) for v in sys.argv[1:]] or [1]
    target = RUNS_DIR / "cpu_reference" / "cpu_reference.json"
    summary = run(values, target)
    print(json.dumps({"all_passed": summary["all_passed"],
                      "M": [c["M"] for c in summary["cases"]],
                      "relative_l2": [c["source_algebra_error"]["relative_l2"] for c in summary["cases"]],
                      "output": str(target)}, indent=2))
