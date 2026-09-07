"""Exact shapes/bytes/operation accounting, not a performance experiment."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    qwen = json.loads((ROOT / "qwen/config.json").read_text())["text_config"]
    flux = json.loads((ROOT / "flux/config.json").read_text())
    qh, qi = qwen["hidden_size"], qwen["intermediate_size"]
    fh = flux["num_attention_heads"] * flux["attention_head_dim"]
    fi = int(fh * flux["mlp_ratio"])
    n = 128
    projections = []
    for name, k, full_n in [
        ("qwen_gate_or_up", qh, qi),
        ("qwen_gqa_q_plus_gate", qh, 2 * qwen["num_attention_heads"] * qwen["head_dim"]),
        ("qwen_gqa_k_or_v", qh, qwen["num_key_value_heads"] * qwen["head_dim"]),
        ("qwen_gqa_o", qwen["num_attention_heads"] * qwen["head_dim"], qh),
        ("qwen_ffn_down", qi, qh),
        ("flux_double_gate_or_up", fh, fi),
        ("flux_double_down", fi, fh),
        ("flux_single_linear1", fh, 3 * fh + 2 * fi),
        ("flux_single_linear2", fh + fi, fh),
    ]:
        projections.append({
            "name": name, "K": k, "N_tile": n, "full_N": full_n,
            "weight_shape": [n, k], "weight_dtype": "BF16",
            "weight_bytes": 2 * k * n,
            "weight_bytes_formula": "2*K*N_tile; full K, selected output columns only",
            "arithmetic": {str(m): {"M": m, "MACs": m * k * n, "FLOPs_MAC2_convention": 2 * m * k * n, "input_bytes_BF16": 2 * m * k, "output_bytes_BF16": 2 * m * n, "accumulator_bytes_FP32": 4 * m * n} for m in [1, 16, 64]},
        })
    kd, vd = qwen["linear_key_head_dim"], qwen["linear_value_head_dim"]
    states = [{"value_heads": heads, "state_shape": [1, heads, kd, vd], "state_dtype": "FP32", "state_bytes": 4 * heads * kd * vd, "minimum_spilled_state_read_write_bytes_per_token": 8 * heads * kd * vd, "core_scalar_add_multiply_count_per_token": 7 * heads * kd * vd, "operation_count_excludes": ["exp", "q/k l2norm", "query scale", "sigmoid/softplus", "conv", "RMSNorm gated", "projections"], "spill_is_assumed_not_mandatory": True} for heads in [1, 2, qwen["linear_num_value_heads"]]]
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / "qwen/config.json", ROOT / "qwen/modeling_qwen3_5.py", ROOT / "flux/config.json", ROOT / "flux/model.py"]}
    payload = {"evidence_level": "source-derived formulas only, no model quality or hardware latency claim", "shape_scope": "full reduction/state dimensions, selected output tiles/heads, not complete model/layer", "source_sha256": sources, "projection_tiles": projections, "qwen_recurrent_states": states, "qwen_two_value_heads_share_one_key_query_head": True, "bytes_do_not_include_padding_compression_or_quantization_metadata": True}
    (ROOT / "fullwidth_shape_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"projections": len(projections), "state_cases": len(states), "Qwen_gate_tile_bytes": projections[0]["weight_bytes"], "Flux_gate_tile_bytes": projections[5]["weight_bytes"]}))


if __name__ == "__main__":
    main()
