"""Full-K/real-head-dimension numerical slices, independent of the R5 simulator.

No trained weights or official framework kernels are executed. BF16 inputs are
rounded in software and stored losslessly in FP32 NumPy containers. Intermediate
projection, activation, and recurrent arithmetic is explicitly FP32.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (51007, 51019, 51031)
PROJECTION_TOLERANCE = {"atol": 1e-5, "rtol": 5e-5}
RECURRENCE_TOLERANCE = {"atol": 2e-6, "rtol": 2e-5}
QWEN_REV = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
TF_REV = "f62dc9bf2c90353b442a56e74391fbb8c689b55e"
FLUX_REV = "e7b7dc27f91deacad38e78976d1f2b499d76a294"
BFL_REV = "50fe5162777813d869182b139e83b10743caef15"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bf16_rne(values: np.ndarray) -> np.ndarray:
    """Round finite FP32 to BF16 round-to-nearest, ties-to-even, then widen."""
    x = np.asarray(values, dtype=np.float32)
    if not np.all(np.isfinite(x)):
        raise ValueError("The random-fixture converter only accepts finite FP32")
    bits = x.view(np.uint32)
    rounded = (bits + np.uint32(0x7FFF) + ((bits >> 16) & 1)) & np.uint32(0xFFFF0000)
    return rounded.view(np.float32)


def bf16_tie_probe() -> dict:
    raw = np.array([0x3F808000, 0x3F818000, 0xBF808000, 0xBF818000,
                    0x00000000, 0x80000000], dtype=np.uint32)
    expected = np.array([0x3F800000, 0x3F820000, 0xBF800000, 0xBF820000,
                         0x00000000, 0x80000000], dtype=np.uint32)
    actual = bf16_rne(raw.view(np.float32)).view(np.uint32)
    assert np.array_equal(actual, expected)
    return {"status": "PASS", "cases": len(raw),
            "scope": "positive/negative halfway ties and signed zero; finite fixture converter"}


def tensor_record(x: np.ndarray, storage: str) -> dict:
    if storage == "BF16":
        assert x.dtype == np.float32 and np.all((x.view(np.uint32) & 0xFFFF) == 0)
        payload = (x.view(np.uint32) >> 16).astype("<u2").tobytes()
    else:
        assert storage == "FP32" and x.dtype == np.float32
        payload = x.astype("<f4", copy=False).tobytes()
    return {"shape": list(x.shape), "storage_dtype": storage,
            "logical_storage_bytes": len(payload), "numpy_container_bytes": x.nbytes,
            "sha256_little_endian_payload": sha(payload)}


def compare(actual: np.ndarray, reference: np.ndarray, tolerance: dict) -> dict:
    assert actual.shape == reference.shape
    assert actual.dtype == reference.dtype == np.float32
    assert np.all(np.isfinite(actual)) and np.all(np.isfinite(reference))
    error = np.abs(actual.astype(np.float64) - reference.astype(np.float64))
    allowed = tolerance["atol"] + tolerance["rtol"] * np.abs(reference.astype(np.float64))
    passed = bool(np.all(error <= allowed))
    result = {"status": "PASS" if passed else "FAIL", **tolerance,
              "elements": actual.size, "max_abs_error": float(error.max(initial=0)),
              "rms_error": float(np.sqrt(np.mean(error * error))),
              "max_error_over_allowed": float(np.max(error / allowed, initial=0))}
    assert passed, result
    return result


def tiled_gateup(x: np.ndarray, packed: np.ndarray, k_step: int) -> tuple[np.ndarray, np.ndarray]:
    projections, activations = [], []
    for core in range(packed.shape[0]):
        acc = np.zeros((x.shape[0], packed.shape[-1]), dtype=np.float32)
        for start in range(0, x.shape[1], k_step):
            part = np.matmul(x[:, start:start + k_step], packed[core, start:start + k_step])
            np.add(acc, part, out=acc)
        gate, up = np.split(acc, 2, axis=-1)
        silu = gate / (np.float32(1) + np.exp(-gate))
        projections.append(acc)
        activations.append(silu * up)
    return np.stack(projections), np.stack(activations)


def full_k_reference(x: np.ndarray, packed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # Untiled, separate gate/up matrices and one full-K BLAS dot per projection.
    # This does not call the tiled path or reproduce its K partial-sum order.
    half = packed.shape[-1] // 2
    gates = np.concatenate([weight[:, :half] for weight in packed], axis=1)
    ups = np.concatenate([weight[:, half:] for weight in packed], axis=1)
    gate = np.dot(x, gates)
    up = np.dot(x, ups)
    activation = (gate / (np.float32(1) + np.exp(-gate))) * up
    output = np.stack([np.concatenate((gate[:, i*half:(i+1)*half], up[:, i*half:(i+1)*half]), axis=1)
                       for i in range(packed.shape[0])])
    act = np.stack([activation[:, i*half:(i+1)*half] for i in range(packed.shape[0])])
    return output, act


def check_projection(name: str, m: int, k: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    x_raw = rng.normal(0, 0.3, (m, k)).astype(np.float32)
    w_raw = rng.normal(0, 0.35 / np.sqrt(k), (2, k, 128)).astype(np.float32)
    x, weight = bf16_rne(x_raw), bf16_rne(w_raw)
    x_before, w_before = sha(x.tobytes()), sha(weight.tobytes())
    projected, activated = tiled_gateup(x, weight, 128)
    ref_projected, ref_activated = full_k_reference(x, weight)
    assert x_before == sha(x.tobytes()) and w_before == sha(weight.tobytes())
    return {"case": name, "seed": seed,
            "projection": compare(projected, ref_projected, PROJECTION_TOLERANCE),
            "swiglu": compare(activated, ref_activated, PROJECTION_TOLERANCE),
            "inputs_unchanged": True,
            "bf16_rounding_max_abs_input": float(np.max(np.abs(x.astype(float) - x_raw))),
            "bf16_rounding_max_abs_weight": float(np.max(np.abs(weight.astype(float) - w_raw))),
            "tensors": {"x": tensor_record(x, "BF16"), "packed_weight": tensor_record(weight, "BF16"),
                        "projection_fp32": tensor_record(projected, "FP32"),
                        "swiglu_fp32": tensor_record(activated, "FP32")}}


def recurrent_vector(q, k, value, beta, g, initial_state):
    state = initial_state.copy()
    outputs, states = [], []
    for token in range(q.shape[0]):
        state = state * np.exp(g[token])[:, None, None]
        prediction = np.sum(state * k[token, :, :, None], axis=1, dtype=np.float32)
        delta = (value[token] - prediction) * beta[token, :, None]
        state = state + k[token, :, :, None] * delta[:, None, :]
        outputs.append(np.sum(state * q[token, :, :, None], axis=1, dtype=np.float32))
        states.append(state.copy())
    return np.stack(outputs), np.stack(states)


def recurrent_scalar_reference(q, k, value, beta, g, initial_state):
    # Independent token/head/key/value loops with explicitly rounded FP32
    # multiply then add. No vector recurrence or reduction helper is called.
    state = initial_state.copy()
    outputs = np.zeros_like(value)
    states = np.zeros((q.shape[0], *state.shape), dtype=np.float32)
    for token in range(q.shape[0]):
        for head in range(state.shape[0]):
            decay = np.float32(np.exp(g[token, head]))
            for key_dim in range(state.shape[1]):
                for value_dim in range(state.shape[2]):
                    state[head, key_dim, value_dim] = np.float32(state[head, key_dim, value_dim] * decay)
            for value_dim in range(state.shape[2]):
                prediction = np.float32(0)
                for key_dim in range(state.shape[1]):
                    product = np.float32(k[token, head, key_dim] * state[head, key_dim, value_dim])
                    prediction = np.float32(prediction + product)
                innovation = np.float32(value[token, head, value_dim] - prediction)
                delta = np.float32(beta[token, head] * innovation)
                output = np.float32(0)
                for key_dim in range(state.shape[1]):
                    update = np.float32(k[token, head, key_dim] * delta)
                    state[head, key_dim, value_dim] = np.float32(state[head, key_dim, value_dim] + update)
                    product = np.float32(q[token, head, key_dim] * state[head, key_dim, value_dim])
                    output = np.float32(output + product)
                outputs[token, head, value_dim] = output
        states[token] = state
    return outputs, states


def check_recurrence(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    # Two adjacent value heads share one Q/K head under repeat_interleave(2).
    raw_q = rng.normal(0, 1, (4, 1, 128)).astype(np.float32)
    raw_k = rng.normal(0, 1, (4, 1, 128)).astype(np.float32)
    q = raw_q / np.sqrt(np.sum(raw_q * raw_q, axis=-1, keepdims=True) + np.float32(1e-6))
    q = np.repeat(q / np.float32(np.sqrt(128)), 2, axis=1)
    k = np.repeat(raw_k / np.sqrt(np.sum(raw_k * raw_k, axis=-1, keepdims=True) + np.float32(1e-6)), 2, axis=1)
    value = rng.normal(0, 0.25, (4, 2, 128)).astype(np.float32)
    beta = rng.uniform(0.05, 0.95, (4, 2)).astype(np.float32)
    g = -rng.uniform(0.01, 0.2, (4, 2)).astype(np.float32)
    state = rng.normal(0, 0.1, (2, 128, 128)).astype(np.float32)
    inputs = {"q_prepared": q, "k_prepared": k, "v_prepared": value,
              "beta_prepared": beta, "g_prepared": g, "S_initial": state}
    before = {name: sha(x.tobytes()) for name, x in inputs.items()}
    actual_o, actual_states = recurrent_vector(q, k, value, beta, g, state)
    ref_o, ref_states = recurrent_scalar_reference(q, k, value, beta, g, state)
    assert before == {name: sha(x.tobytes()) for name, x in inputs.items()}
    return {"case": "qwen35_gdn_two_value_heads_four_tokens", "seed": seed,
            "o_all_tokens": compare(actual_o, ref_o, RECURRENCE_TOLERANCE),
            "S_every_token": compare(actual_states, ref_states, RECURRENCE_TOLERANCE),
            "inputs_unchanged": True,
            "tensors": {**{name: tensor_record(x, "FP32") for name, x in inputs.items()},
                        "o_all_tokens": tensor_record(actual_o, "FP32"),
                        "S_final": tensor_record(actual_states[-1], "FP32")}}


def freeze_sources() -> list[dict]:
    sources = []
    for folder, manifest, chosen in (
        ("r4/sources/qwen", "manifest.json", {"config.json", "modeling_qwen3_5.py"}),
        ("r4/sources/flux", "source_manifest.json", {
            "FLUX.2-klein-4B/transformer/config.json", "black-forest-labs__flux2/src/flux2/model.py"}),
    ):
        data = json.loads((ROOT / folder / manifest).read_text(encoding="utf-8"))
        for row in data["files"]:
            rel = row.get("file", row.get("path"))
            if rel in chosen:
                path = ROOT / folder / rel
                assert sha(path.read_bytes()) == row["sha256"], path
                sources.append({"local_path": path.relative_to(ROOT).as_posix(),
                                "sha256": row["sha256"], "url": row["url"],
                                "bytes": path.stat().st_size,
                                "inherited_manifest": f"{folder}/{manifest}"})
    assert len(sources) == 4
    return sources


def projection_spec(name, m, k, source):
    return {"case": name, "M": m, "K_full": k, "K_step": 128,
            "cores": 2, "packed_N_per_core": 128, "gate_N_per_core": 64, "up_N_per_core": 64,
            "K_steps": k // 128, "full_intermediate_width": 9216,
            "selected_intermediate_indices": [[0, 64], [64, 128]], "selected_ranges_half_open": True,
            "input_prepared": "post-normalization/modulation input; no norm or residual included",
            "layout": "row-major x[M,K], packed W[core,K,gate64+up64]; transpose of checkpoint Linear [out,in]",
            "storage": "BF16 x/W; FP32 projection accumulator and SwiGLU output; no implicit BF16 output recast",
            "exact_dense_MACs": m * k * 128 * 2,
            "logical_bytes": {"shared_x": m*k*2, "weights_both_cores": 2*k*128*2,
                              "FP32_projection_both_cores": 2*m*128*4,
                              "FP32_SwiGLU_both_cores": 2*m*64*4},
            "per_Kstep_per_core_bytes": {"activation_tile": m*128*2, "weight_tile": 128*128*2,
                                          "FP32_accumulator": m*128*4},
            "traffic_boundary": "logical payloads and tile sizes, not a measured transfer count; core replication/prefetch/reuse depend on performance contract",
            "source": source,
            "scope": "complete source K dimension and two legal output-axis slices; not the full FFN, down projection, block or model; M is a token-row tile"}


def main():
    sources = freeze_sources()
    qconfig = json.loads((ROOT / "r4/sources/qwen/config.json").read_text())["text_config"]
    fconfig = json.loads((ROOT / "r4/sources/flux/FLUX.2-klein-4B/transformer/config.json").read_text())
    assert qconfig["hidden_size"] == 2560 and qconfig["intermediate_size"] == 9216
    assert qconfig["linear_key_head_dim"] == qconfig["linear_value_head_dim"] == 128
    assert fconfig["attention_head_dim"] * fconfig["num_attention_heads"] == 3072
    assert fconfig["mlp_ratio"] * 3072 == 9216
    specs = {"evidence_level": "source-derived full-K output slices and real-dimensional recurrent heads, random numerical validation only",
             "models": {"Qwen/Qwen3.5-4B": {"revision": QWEN_REV, "implementation_revision": TF_REV, "license": "Apache-2.0"},
                        "black-forest-labs/FLUX.2-klein-4B": {"revision": FLUX_REV, "implementation_revision": BFL_REV, "license": "Apache-2.0", "distilled": True, "CFG": 1}},
             "source_files": sources, "seeds": list(SEEDS),
             "qwen_projection": projection_spec("qwen35_fullK_gateup_slice", 1, 2560,
                  f"https://github.com/huggingface/transformers/blob/{TF_REV}/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L822-L834"),
             "flux_projection": projection_spec("flux2_fullK_gateup_token_tile", 32, 3072,
                  f"https://github.com/black-forest-labs/flux2/blob/{BFL_REV}/src/flux2/model.py#L393-L399"),
             "qwen_gdn": {"case": "qwen35_gdn_two_value_heads_four_tokens", "tokens": 4, "batch": 1,
                 "source_value_heads": 32, "selected_value_heads": [0, 1], "shared_source_key_head": 0,
                 "Dk": 128, "Dv": 128, "state_layout": "[value_head,key_dim,value_dim]",
                 "input_arithmetic": "FP32 prepared q/k/v/beta/g and FP32 S; q already L2-normalized and divided by sqrt(128), k L2-normalized",
                 "initial_state_bytes": 2*128*128*4, "full_layer_state_bytes": 32*128*128*4,
                 "prepared_vector_bytes": 3*4*2*128*4, "prepared_scalar_bytes": 2*4*2*4,
                 "output_bytes": 4*2*128*4, "final_state_bytes": 2*128*128*4,
                 "MAC_equivalent_reductions_and_outer_updates": 4*2*3*128*128,
                 "additional_elementwise_multiplications": {"state_decay": 4*2*128*128, "beta": 4*2*128},
                 "source": f"https://github.com/huggingface/transformers/blob/{TF_REV}/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L436-L495",
                 "scope": "four recurrent decode steps on two real-dimensional heads; excludes upstream projection/conv, qk normalization, beta/g generation, output norm/gating/out projection; not chunked prefill"},
             "limitations": ["No trained weights, full-model quality, official PyTorch/Transformers execution, production compiler or NPU validation",
                 "Full K/head dimensions do not mean full layer/model workload coverage",
                 "FP32 NumPy reduction order is not a claimed physical MXU implementation or bitwise official BF16 kernel match",
                 "Numerical payload hashes/specs are independent from request-level performance traces; no address/physical execution equivalence asserted"],
             "numerical_source_sha256": sha(Path(__file__).read_bytes())}
    tie = bf16_tie_probe()
    checks = []
    for seed in SEEDS:
        checks.append(check_projection("qwen35_fullK_gateup_slice", 1, 2560, seed))
        checks.append(check_projection("flux2_fullK_gateup_token_tile", 32, 3072, seed))
        checks.append(check_recurrence(seed))
    specs_path = ROOT / "r5/full_width_specs.json"
    specs_path.write_text(json.dumps(specs, ensure_ascii=False, indent=2), encoding="utf-8")
    all_comparisons = [v for row in checks for v in row.values() if isinstance(v, dict) and "max_abs_error" in v]
    result = {"status": "PASS", "python": platform.python_version(), "numpy": np.__version__,
              "source_sha256": specs["numerical_source_sha256"], "specs_sha256": sha(specs_path.read_bytes()),
              "checks": checks, "datasets": len(checks), "comparisons": len(all_comparisons),
              "max_abs_error": max(x["max_abs_error"] for x in all_comparisons), "BF16_RNE_probe": tie,
              "tolerance_policy": {"projection_and_SwiGLU": PROJECTION_TOLERANCE, "recurrent_state_and_output": RECURRENCE_TOLERANCE,
                  "interpretation": "fixed before runs; tests FP32 accumulation/reassociation on identical BF16-rounded projection inputs, and FP32 state recurrence. atol handles near zero; rtol handles scale. Does not bound BF16-vs-FP32 model error or trained-model quality."},
              "scope": specs["evidence_level"], "limitations": specs["limitations"]}
    (ROOT / "r5/numerical_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "datasets": len(checks), "comparisons": len(all_comparisons),
                      "max_abs_error": result["max_abs_error"], "source_sha256": result["source_sha256"],
                      "specs_sha256": result["specs_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
