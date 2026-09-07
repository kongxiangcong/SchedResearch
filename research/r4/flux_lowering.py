"""Source-derived, scaled FLUX.2 Klein 4B block graphs (random float64 only).

The official model is 3072-wide; these 64-wide graphs test mathematical
lowering, not model quality, official BF16 rounding, or full-model latency.
"""
from __future__ import annotations
import numpy as np
from r4.graph import Case, Node

REVISION = "50fe5162777813d869182b139e83b10743caef15"
SOURCE = f"https://github.com/black-forest-labs/flux2/blob/{REVISION}/src/flux2/model.py"
H, HEADS, D, M, TIME_DIM = 64, 4, 16, 192, 16
AXES = (4, 4, 4, 4)


def _silu(x):
    return x / (1.0 + np.exp(-x))


def _ln(x):
    return (x - x.mean(-1, keepdims=True)) / np.sqrt(x.var(-1, keepdims=True) + 1e-6)


def _time(t):
    freq = np.exp(-np.log(10000) * np.arange(TIME_DIM // 2) / (TIME_DIM // 2))
    a = 1000 * t[:, None] * freq[None]
    return np.concatenate((np.cos(a), np.sin(a)), axis=-1)


def _rope(x, ids):
    result, offset = [], 0
    for axis, width in enumerate(AXES):
        pairs = x[..., offset:offset + width].reshape(*x.shape[:-1], width // 2, 2)
        a = ids[:, None, :, axis, None] * 2000.0 ** (-np.arange(0, width, 2) / width)
        c, s = np.cos(a), np.sin(a)
        result.append(np.stack((pairs[..., 0] * c - pairs[..., 1] * s,
                                pairs[..., 0] * s + pairs[..., 1] * c), axis=-1).reshape(*x.shape[:-1], width))
        offset += width
    return np.concatenate(result, axis=-1)


def _qkv(linear, scale, ids):
    qkv = linear[..., :3 * H].reshape(linear.shape[0], linear.shape[1], 3, HEADS, D).transpose(2, 0, 3, 1, 4)
    q, k, v = qkv
    q = q / np.sqrt(np.mean(q * q, axis=-1, keepdims=True) + 1e-6) * scale[0]
    k = k / np.sqrt(np.mean(k * k, axis=-1, keepdims=True) + 1e-6) * scale[1]
    return np.stack((_rope(q, ids), _rope(k, ids), v))


def _softmax(x):
    z = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return z / z.sum(-1, keepdims=True)


def _ids(length, image=False):
    ids = np.zeros((1, length, 4))
    if image:
        ids[0, :, 1] = np.arange(length) // 4
        ids[0, :, 2] = np.arange(length) % 4
    else:
        ids[0, :, 3] = np.arange(length)
    return ids


def _weight(rng, rows, cols):
    return rng.normal(0, 0.35 / np.sqrt(rows), (rows, cols))


def _condition(initial, nodes, rng, streams):
    initial.update({"timestep": np.array([0.7]), "time_w1": _weight(rng, TIME_DIM, H),
                    "time_w2": _weight(rng, H, H)})
    nodes.extend([
        Node("timestep_embedding", "VPU", ("timestep",), ("time_emb",), _time,
             vector_ops=TIME_DIM * 8, source=SOURCE + "#L707", fusion="sinusoidal timestep embedding; scaled 16 channels"),
        Node("time_linear1", "MXU", ("time_emb", "time_w1"), ("time_hidden",), np.matmul,
             macs=TIME_DIM * H, source=SOURCE + "#L683", fusion="bias-free MLP first projection"),
        Node("time_silu1", "VPU", ("time_hidden",), ("time_hidden_act",), _silu,
             vector_ops=H * 5, source=SOURCE + "#L690", fusion="SiLU"),
        Node("time_linear2", "MXU", ("time_hidden_act", "time_w2"), ("time_vec",), np.matmul,
             macs=H * H, source=SOURCE + "#L690", fusion="bias-free MLP second projection"),
        Node("modulation_silu", "VPU", ("time_vec",), ("modulation_input",), _silu,
             vector_ops=H * 5, source=SOURCE + "#L407", fusion="shared SiLU reused by both stream modulation projections"),
    ])
    for stream, multiplier, core in streams:
        initial[f"{stream}_mod_weight"] = _weight(rng, H, multiplier * H)
        nodes.append(Node(f"{stream}_modulation", "MXU", ("modulation_input", f"{stream}_mod_weight"),
                          (f"{stream}_mod",), lambda a, w, n=multiplier: (a @ w).reshape(1, 1, n, H),
                          macs=multiplier * H * H, source=SOURCE + "#L400",
                          fusion="one packed shift/scale/gate tensor; actual model reuses across all same-type blocks", core=core))


def _reference(initial, kind):
    """Independent direct block formulas; does not execute/call any Node.run."""
    # Deliberately spell out the conditioning, normalizations, and attention.
    f = np.power(10000.0, -np.arange(TIME_DIM // 2) / (TIME_DIM // 2))
    a = initial["timestep"][:, None] * 1000 * f
    te = np.concatenate([np.cos(a), np.sin(a)], axis=-1)
    y = te @ initial["time_w1"]
    vec = (y / (1 + np.exp(-y))) @ initial["time_w2"]
    mod_input = vec / (1 + np.exp(-vec))

    def norm(x):
        centered = x - np.sum(x, axis=-1, keepdims=True) / x.shape[-1]
        return centered / np.sqrt(np.sum(centered ** 2, axis=-1, keepdims=True) / x.shape[-1] + 1e-6)

    def rotary(x, ids):
        out = x.copy()
        start = 0
        for axis, width in enumerate(AXES):
            for pair in range(width // 2):
                angle = ids[:, None, :, axis] / (2000 ** (2 * pair / width))
                even, odd = start + 2 * pair, start + 2 * pair + 1
                out[..., even] = x[..., even] * np.cos(angle) - x[..., odd] * np.sin(angle)
                out[..., odd] = x[..., even] * np.sin(angle) + x[..., odd] * np.cos(angle)
            start += width
        return out

    def qkv(y, scales, ids):
        pieces = np.split(y[..., :3 * H], 3, axis=-1)
        q, k, v = [z.reshape(1, z.shape[1], HEADS, D).transpose(0, 2, 1, 3) for z in pieces]
        q = q * np.reciprocal(np.sqrt((q ** 2).mean(-1, keepdims=True) + 1e-6)) * scales[0]
        k = k * np.reciprocal(np.sqrt((k ** 2).mean(-1, keepdims=True) + 1e-6)) * scales[1]
        return rotary(q, ids), rotary(k, ids), v

    def attend(q, k, v):
        logits = np.matmul(q, k.swapaxes(-1, -2)) * D ** -0.5
        exp = np.exp(logits - logits.max(-1, keepdims=True))
        return (np.matmul(exp / exp.sum(-1, keepdims=True), v)).transpose(0, 2, 1, 3).reshape(1, q.shape[2], H)

    if kind == "double":
        states, mods, qs = {}, {}, {}
        for s in ("img", "txt"):
            x = initial[f"{s}_input"] @ initial[f"{s}_input_weight"]
            mods[s] = (mod_input @ initial[f"{s}_mod_weight"]).reshape(1, 1, 6, H)
            m = mods[s]
            y = norm(x) * (1 + m[..., 1, :]) + m[..., 0, :]
            qs[s] = qkv(y @ initial[f"{s}_qkv_weight"], initial[f"{s}_qk_scale"], initial[f"{s}_ids"])
            states[s] = x
        all_k = np.concatenate([qs["txt"][1], qs["img"][1]], axis=2)
        all_v = np.concatenate([qs["txt"][2], qs["img"][2]], axis=2)
        result = {}
        for s in ("img", "txt"):
            m = mods[s]
            x = states[s] + m[..., 2, :] * (attend(qs[s][0], all_k, all_v) @ initial[f"{s}_proj_weight"])
            y = norm(x) * (1 + m[..., 4, :]) + m[..., 3, :]
            gate, value = np.split(y @ initial[f"{s}_mlp1_weight"], 2, axis=-1)
            result[f"{s}_out"] = x + m[..., 5, :] * (((gate / (1 + np.exp(-gate))) * value) @ initial[f"{s}_mlp2_weight"])
        return result
    x = initial["x"]
    mod = (mod_input @ initial["single_mod_weight"]).reshape(1, 1, 3, H)
    lin = ((1 + mod[..., 1, :]) * norm(x) + mod[..., 0, :]) @ initial["linear1_weight"]
    q, k, v = qkv(lin, initial["qk_scale"], initial["ids"])
    gate, value = np.split(lin[..., 3 * H:], 2, axis=-1)
    mlp = (gate / (1 + np.exp(-gate))) * value
    return {"out": x + mod[..., 2, :] * (np.concatenate([attend(q, k, v), mlp], -1) @ initial["linear2_weight"])}


def _metadata(kind):
    return {"model": "black-forest-labs/FLUX.2-klein-4B", "revision": "e7b7dc27f91deacad38e78976d1f2b499d76a294",
            "source_revision": REVISION, "kind": kind, "scope": "scaled single block; random-weight mathematical float64 check; no quality or official dtype rounding validation",
            "actual_hidden_size": 3072, "scaled_hidden_size": H, "actual_heads": 24, "scaled_heads": HEADS,
            "actual_head_dim": 128, "scaled_head_dim": D, "actual_mlp_ratio": 3.0,
            "actual_timestep_embedding_dim": 256, "scaled_timestep_embedding_dim": TIME_DIM,
            "actual_axes_dims": [32, 32, 32, 32], "scaled_axes_dims": list(AXES), "rope_theta": 2000,
            "conditioning": "step+guidance distilled; guidance_embed=False; one conditional invocation, CFG=1; time modulation explicit",
            "reference_tokens": 0, "persistent_kv": False,
            "source_attention": "num_ref_tokens=0 makes txt+img full joint bidirectional attention; no text causal mask",
            "dtype_numeric": "float64", "dtype_model": "BF16", "operation_counts": "MAC exact for selected dense shapes; vector_ops research estimates, not calibrated hardware instructions",
            "fusion_scope": "pointwise norm/modulation and residual epilogues fused; all dense projections retained; no full attention score fusion assumed",
            "full_pipeline_exclusions": ["text encoder", "VAE", "other 24 transformer blocks", "four-step denoising loop", "image editing/ref-cache path"],
            "layout": "activations BLH contiguous; QKV packed 3BHLD; attention BHLS; weight input-by-output for NumPy (transpose of torch Linear storage)"}


def _double(seed):
    rng = np.random.default_rng(seed)
    initial, nodes = {}, []
    _condition(initial, nodes, rng, [("img", 6, 0), ("txt", 6, 1)])
    for s, length, in_dim, core in (("img", 16, 16, 0), ("txt", 8, 96, 1)):
        initial.update({f"{s}_input": rng.normal(size=(1, length, in_dim)),
                        f"{s}_input_weight": _weight(rng, in_dim, H), f"{s}_ids": _ids(length, s == "img"),
                        f"{s}_qkv_weight": _weight(rng, H, 3 * H), f"{s}_qk_scale": rng.normal(1, 0.1, (2, D)),
                        f"{s}_proj_weight": _weight(rng, H, H), f"{s}_mlp1_weight": _weight(rng, H, 2 * M),
                        f"{s}_mlp2_weight": _weight(rng, M, H)})
        nodes.extend([
            Node(f"{s}_input_projection", "MXU", (f"{s}_input", f"{s}_input_weight"), (f"{s}_state",), np.matmul,
                 macs=length * in_dim * H, source=SOURCE + "#L66", fusion="bias-free input projection; source channels scaled", core=core),
            Node(f"{s}_norm_mod1", "VPU", (f"{s}_state", f"{s}_mod"), (f"{s}_normalized1",),
                 lambda x, m: _ln(x) * (1 + m[..., 1, :]) + m[..., 0, :], vector_ops=length * H * 12,
                 source=SOURCE + "#L583", fusion="LayerNorm eps1e-6 plus AdaLN affine", core=core),
            Node(f"{s}_qkv_projection", "MXU", (f"{s}_normalized1", f"{s}_qkv_weight"), (f"{s}_linear",), np.matmul,
                 macs=length * H * 3 * H, source=SOURCE + "#L586", fusion="QKV joint projection", core=core),
            Node(f"{s}_qk_norm_rope", "VPU", (f"{s}_linear", f"{s}_qk_scale", f"{s}_ids"), (f"{s}_qkv",), _qkv,
                 vector_ops=length * H * 28, source=SOURCE + "#L646", fusion="reshape plus head RMSNorm eps1e-6 and 4-axis RoPE; V passthrough", core=core),
        ])
    nodes.append(Node("joint_kv", "VPU", ("txt_qkv", "img_qkv"), ("joint_k", "joint_v"),
                      lambda t, i: (np.concatenate([t[1], i[1]], 2), np.concatenate([t[2], i[2]], 2)),
                      vector_ops=24 * H * 2, source=SOURCE + "#L600", fusion="explicit joint KV gather; text then image layout"))
    for s, length, core in (("img", 16, 0), ("txt", 8, 1)):
        nodes.extend([
            Node(f"{s}_qk", "MXU", (f"{s}_qkv", "joint_k"), (f"{s}_scores",), lambda qkv, k: qkv[0] @ k.swapaxes(-1, -2) / np.sqrt(D),
                 macs=HEADS * length * 24 * D, source=SOURCE + "#L756", fusion="joint attention split by query stream; exact row independence", core=core),
            Node(f"{s}_softmax", "VPU", (f"{s}_scores",), (f"{s}_prob",), _softmax,
                 vector_ops=HEADS * length * 24 * 6, source=SOURCE + "#L756", fusion="stable full-row softmax", core=core),
            Node(f"{s}_av", "MXU", (f"{s}_prob", "joint_v"), (f"{s}_attn",),
                 lambda p, v: (p @ v).transpose(0, 2, 1, 3).reshape(1, p.shape[2], H),
                 macs=HEADS * length * 24 * D, source=SOURCE + "#L756", fusion="attention weighted value plus head merge", core=core),
            Node(f"{s}_attention_out", "MXU", (f"{s}_attn", f"{s}_proj_weight"), (f"{s}_attn_proj",), np.matmul,
                 macs=length * H * H, source=SOURCE + "#L626", fusion="attention output projection", core=core),
            Node(f"{s}_residual_norm2", "VPU", (f"{s}_state", f"{s}_attn_proj", f"{s}_mod"), (f"{s}_residual1", f"{s}_normalized2"),
                 lambda x, a, m: (x + m[..., 2, :] * a, _ln(x + m[..., 2, :] * a) * (1 + m[..., 4, :]) + m[..., 3, :]),
                 vector_ops=length * H * 14, source=SOURCE + "#L626", fusion="gated residual then norm/AdaLN; first residual retained for final skip", core=core),
            Node(f"{s}_mlp_expand", "MXU", (f"{s}_normalized2", f"{s}_mlp1_weight"), (f"{s}_mlp_linear",), np.matmul,
                 macs=length * H * 2 * M, source=SOURCE + "#L549", fusion="packed gate/value projection", core=core),
            Node(f"{s}_swiglu", "VPU", (f"{s}_mlp_linear",), (f"{s}_mlp_act",), lambda z: _silu(z[..., :M]) * z[..., M:],
                 vector_ops=length * M * 6, source=SOURCE + "#L390", fusion="SiLU gate times value; not GELU", core=core),
            Node(f"{s}_mlp_contract", "MXU", (f"{s}_mlp_act", f"{s}_mlp2_weight"), (f"{s}_mlp_out",), np.matmul,
                 macs=length * M * H, source=SOURCE + "#L552", fusion="MLP contraction", core=core),
            Node(f"{s}_residual2", "VPU", (f"{s}_residual1", f"{s}_mlp_out", f"{s}_mod"), (f"{s}_out",),
                 lambda x, y, m: x + m[..., 5, :] * y, vector_ops=length * H * 2,
                 source=SOURCE + "#L627", fusion="gated second residual", core=core),
        ])
    metadata = _metadata("double_stream")
    metadata.update({"scaled_shapes": {"image_tokens": 16, "text_tokens": 8, "input_image_channels": 16, "input_context_channels": 96},
                     "remaining_branches": ["image/text input projection", "image/text QKV preparation", "query-row attention", "image/text postattention and FFN"],
                     "source_input_channels": {"image": 128, "context": 7680}})
    return Case("flux2_klein4b_double_scaled", initial, nodes, ("img_out", "txt_out"), _reference(initial, "double"), metadata)


def _single(seed):
    rng = np.random.default_rng(seed)
    initial, nodes = {}, []
    length = 24
    _condition(initial, nodes, rng, [("single", 3, 0)])
    initial.update({"x": rng.normal(size=(1, length, H)), "ids": np.concatenate([_ids(8), _ids(16, True)], 1),
                    "linear1_weight": _weight(rng, H, 3 * H + 2 * M), "linear2_weight": _weight(rng, H + M, H),
                    "qk_scale": rng.normal(1, 0.1, (2, D))})
    nodes.extend([
        Node("single_norm_mod", "VPU", ("x", "single_mod"), ("normalized",), lambda x, m: _ln(x) * (1 + m[..., 1, :]) + m[..., 0, :],
             vector_ops=length * H * 12, source=SOURCE + "#L465", fusion="LayerNorm plus AdaLN"),
        Node("single_linear1", "MXU", ("normalized", "linear1_weight"), ("linear1",), np.matmul,
             macs=length * H * (3 * H + 2 * M), source=SOURCE + "#L454", fusion="one actual fused QKV and gate/value projection"),
        Node("single_qk_norm_rope", "VPU", ("linear1", "qk_scale", "ids"), ("qkv",), _qkv,
             vector_ops=length * H * 28, source=SOURCE + "#L491", fusion="QKV slice view plus RMSNorm/RoPE"),
        Node("single_swiglu", "VPU", ("linear1",), ("mlp_act",), lambda y: _silu(y[..., 3 * H:3 * H + M]) * y[..., 3 * H + M:],
             vector_ops=length * M * 6, source=SOURCE + "#L481", fusion="independent MLP branch from same linear1 output", core=1),
        Node("single_qk", "MXU", ("qkv",), ("scores",), lambda a: a[0] @ a[1].swapaxes(-1, -2) / np.sqrt(D),
             macs=HEADS * length * length * D, source=SOURCE + "#L756", fusion="full joint bidirectional QK"),
        Node("single_softmax", "VPU", ("scores",), ("prob",), _softmax,
             vector_ops=HEADS * length * length * 6, source=SOURCE + "#L756", fusion="stable full-row softmax"),
        Node("single_av", "MXU", ("prob", "qkv"), ("attn",), lambda p, a: (p @ a[2]).transpose(0, 2, 1, 3).reshape(1, length, H),
             macs=HEADS * length * length * D, source=SOURCE + "#L756", fusion="weighted V plus head merge"),
        Node("single_join_project", "MXU", ("attn", "mlp_act", "linear2_weight"), ("projected",), lambda a, m, w: np.concatenate([a, m], -1) @ w,
             macs=length * (H + M) * H, source=SOURCE + "#L481", fusion="linear2 consumes attention and MLP slices; concatenation staging assumed fusible"),
        Node("single_residual", "VPU", ("x", "projected", "single_mod"), ("out",), lambda x, p, m: x + m[..., 2, :] * p,
             vector_ops=length * H * 2, source=SOURCE + "#L483", fusion="gated residual"),
    ])
    metadata = _metadata("single_stream")
    metadata.update({"scaled_shapes": {"image_tokens": 16, "text_tokens": 8},
                     "remaining_branches": ["attention QK/softmax/AV and SiLU-gated MLP after fused linear1"],
                     "input_scope": "already-projected and concatenated text/image states at one single-block boundary"})
    return Case("flux2_klein4b_single_scaled", initial, nodes, ("out",), _reference(initial, "single"), metadata)


def build_cases(seed=7) -> list[Case]:
    return [_double(seed), _single(seed + 1)]


def _aggregate_attention(stages):
    """Compose an exact three-stage attention slice, hiding its scratch tensors.

    This is an aggregate kernel boundary sensitivity, not an implementation of
    FlashAttention. The simulator must charge summed stage service and reserve
    MXU+VPU resources conservatively for the whole aggregate operation.
    """
    internal = {k for n in stages for k in n.writes}
    reads = tuple(dict.fromkeys(k for n in stages for k in n.reads if k not in internal))
    writes = stages[-1].writes

    def execute(*args):
        values = dict(zip(reads, args))
        for n in stages:
            result = n.run(*(values[k] for k in n.reads))
            results = (result,) if len(n.writes) == 1 else result
            values.update(zip(n.writes, results))
        return values[writes[0]] if len(writes) == 1 else tuple(values[k] for k in writes)

    return Node(stages[0].name + "_softmax_av_aggregate", "MXU+VPU", reads, writes, execute,
                macs=sum(n.macs for n in stages), vector_ops=sum(n.vector_ops for n in stages),
                source="; ".join(dict.fromkeys(n.source for n in stages)),
                fusion="QK -> softmax -> AV aggregate; summed stage service; atomic MXU+VPU+SRAM reservation; internal scores/probability scratch abstracted, not a FlashAttention kernel",
                core=stages[0].core)


def build_optimized_cases(seed=7) -> list[Case]:
    """Joint attention fusion and conditioning-resident boundary sensitivity.

    Each denoising step still pays for the shared timestep/modulation producer
    once outside this single-block slice. Its final modulation tensors become
    initial block inputs; the compiler/harness must still charge their loads.
    """
    optimized = []
    for original in build_cases(seed):
        original_values = original.evaluate()
        conditional_names = {"timestep_embedding", "time_linear1", "time_silu1", "time_linear2", "modulation_silu",
                             "img_modulation", "txt_modulation", "single_modulation"}
        dropped = [n for n in original.nodes if n.name in conditional_names]
        mod_keys = ("img_mod", "txt_mod") if original.metadata["kind"] == "double_stream" else ("single_mod",)
        initial = {k: v.copy() for k, v in original.initial.items()}
        initial.update({k: original_values[k].copy() for k in mod_keys})
        node_map = {n.name: n for n in original.nodes}
        prefixes = ("img", "txt") if len(mod_keys) == 2 else ("single",)
        replacement = {}
        internal_scratch = {}
        removed = set(conditional_names)
        for prefix in prefixes:
            names = [f"{prefix}_qk", f"{prefix}_softmax", f"{prefix}_av"]
            aggregate = _aggregate_attention([node_map[n] for n in names])
            replacement[names[0]] = aggregate
            scratch_keys = [k for name in names[:-1] for k in node_map[name].writes]
            scratch_bytes = sum(original_values[k].size * 2 for k in scratch_keys)
            internal_scratch[aggregate.name] = {
                "bytes": int(scratch_bytes),
                "traffic_bytes": int(2 * scratch_bytes),
                "scope": "materialized engine-internal scratch, not online FlashAttention",
                "tensors": scratch_keys,
                "dtype_assumption": "BF16; capacity conservatively sums scores and probability, internal read and write each counted once",
            }
            removed.update(names[1:])
        nodes = [replacement.get(n.name, n) for n in original.nodes if n.name not in removed]
        consumed_initial = {k for n in nodes for k in n.reads}
        initial = {k: v for k, v in initial.items() if k in consumed_initial}
        metadata = dict(original.metadata)
        metadata.update({
            "optimization_boundary": "aggregate attention and conditioning-resident single-block slice",
            "conditioning_scope": "timestep/time-MLP/modulation computed once per denoising step outside this block; final modulation read loads remain; excluded producer costs must be charged once in any full-pipeline extrapolation",
            "outside_boundary_nodes": [n.name for n in dropped],
            "outside_boundary_macs": sum(n.macs for n in dropped),
            "outside_boundary_vector_ops_estimate": sum(n.vector_ops for n in dropped),
            "internal_scratch": internal_scratch,
            "attention_fusion_scope": "exact numerical QK-softmax-AV composition, scratch lifetimes hidden; cost is summed stage service with full-duration atomic reservation of MXU+VPU+SRAM, not verified FlashAttention performance",
            "base_case": original.name,
        })
        optimized.append(Case(original.name + "_attention_aggregate_cond_resident", initial, nodes,
                              original.outputs, original.reference, metadata))
    return optimized


if __name__ == "__main__":
    import json
    for case in build_cases() + build_optimized_cases():
        actual = case.evaluate()
        errors = {name: float(np.max(np.abs(actual[name] - reference))) for name, reference in case.reference.items()}
        assert max(errors.values()) < 1e-11, errors
        print(json.dumps({"case": case.name, "nodes": len(case.nodes), "maximum_absolute_error": errors}))
