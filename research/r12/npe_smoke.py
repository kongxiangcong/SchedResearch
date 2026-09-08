"""Run the pinned upstream example through tt-npe's documented Python API.

Only estimator execution is qualified. Values are not native hardware timings.
The example's embedded golden values have not been independently measured here.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("/opt/schedresearch-r12/tt-npe"))
    parser.add_argument("--install", type=Path, default=Path("/opt/schedresearch-r12/install/tt-npe"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "schema": "r12-npe-smoke-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "evidence_level": "official coarse estimator and upstream example workload",
        "hardware_measurement": False,
        "golden_reference_independently_verified": False,
        "full_dfg_timing_calibrated": False,
    }
    try:
        import tt_npe_pybind as npe

        module_path = Path(npe.__file__).resolve()
        if not module_path.is_relative_to((args.install / "lib").resolve()):
            raise RuntimeError(f"Wrong NPE binary loaded: {module_path}")
        workload_path = args.source / "tt_npe/workload/example_wl.json"
        result["module"] = str(module_path)
        result["workload"] = {"path": str(workload_path), "sha256": hashlib.sha256(workload_path.read_bytes()).hexdigest()}
        cfg = npe.Config()
        cfg.device_name = "wormhole_b0"
        cfg.congestion_model_name = "fast"
        cfg.cycles_per_timestep = 32
        cfg.infer_injection_rate_from_src = True
        cfg.workload_json_filepath = str(workload_path)
        result["config"] = {"device": "wormhole_b0", "congestion_model": "fast", "cycles_per_timestep": 32, "injection_rate_inference": True}
        workload = npe.createWorkloadFromJSON(str(workload_path), cfg.device_name)
        if workload is None:
            raise RuntimeError("Upstream example workload could not be parsed")
        api = npe.InitAPI(cfg)
        if api is None:
            raise RuntimeError("NPE API initialization failed")
        stats = api.runNPE(workload)
        if not isinstance(stats, npe.Stats):
            raise RuntimeError(f"NPE did not return Stats: {stats}")
        result["per_device_stats"] = {}
        fields = (
            "completed", "estimated_cycles", "estimated_cong_free_cycles", "golden_cycles",
            "cycle_prediction_error", "wallclock_runtime_us", "dram_bw_util", "dram_bw_util_sim",
            "overall_avg_noc0_link_util", "overall_avg_noc1_link_util",
            "overall_avg_niu_demand", "overall_max_niu_demand",
        )
        for device_id, values in stats.per_device_stats.items():
            record = {field: getattr(values, field) for field in fields}
            record["dram_bw_util_per_controller"] = dict(values.dram_bw_util_per_controller)
            result["per_device_stats"][str(device_id)] = record
            if not values.completed or values.estimated_cycles <= 0:
                raise RuntimeError(f"Invalid completion or estimated cycles for device {device_id}")
        if not result["per_device_stats"]:
            raise RuntimeError("NPE returned no per-device statistics")
        result["passed"] = True
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
