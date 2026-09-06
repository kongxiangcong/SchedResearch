"""Exact dense trainable parameter counts from frozen configs and BFL source."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def conv(i, o, k=3):
    return i * o * k * k + o


def resblock(i, o):
    return 2 * i + conv(i, o) + 2 * o + conv(o, o) + (conv(i, o, 1) if i != o else 0)


def attn(c):
    return 2 * c + 4 * conv(c, c, 1)


def main():
    cfg = json.loads((ROOT / "FLUX.2-klein-4B/transformer/config.json").read_text())
    h = cfg["num_attention_heads"] * cfg["attention_head_dim"]
    d = cfg["attention_head_dim"]
    main_parts = {
        "image_projection": cfg["in_channels"] * h,
        "text_projection": cfg["joint_attention_dim"] * h,
        "timestep_mlp": cfg["timestep_guidance_channels"] * h + h * h,
        "double_blocks": cfg["num_layers"] * (26 * h * h + 4 * d),
        "single_blocks": cfg["num_single_layers"] * (13 * h * h + 2 * d),
        "shared_modulation": 15 * h * h,
        "final_layer": 2 * h * h + h * cfg["in_channels"],
    }
    main_count = sum(main_parts.values())
    api = json.loads((ROOT / "FLUX.2-klein-4B/api_model.json").read_text())
    assert main_count == api["safetensors"]["total"]
    c = json.loads((ROOT / "FLUX.2-klein-4B/text_encoder/config.json").read_text())
    hq, dq = c["hidden_size"], c["head_dim"]
    attn_params = hq * dq * (2 * c["num_attention_heads"] + 2 * c["num_key_value_heads"]) + 2 * dq
    per_layer = attn_params + 3 * hq * c["intermediate_size"] + 2 * hq
    text_count = c["vocab_size"] * hq + c["num_hidden_layers"] * per_layer + hq
    assert c["tie_word_embeddings"]
    text_index = json.loads((ROOT / "FLUX.2-klein-4B/text_encoder/model.safetensors.index.json").read_text())
    assert text_count == text_index["metadata"]["total_parameters"]
    # AutoEncoderParams/default topology in the pinned official autoencoder.py.
    levels = [128, 256, 512, 512]
    encoder = conv(3, 128) + conv(64, 64, 1)
    block_in = 128
    for index, block_out in enumerate(levels):
        for _ in range(2):
            encoder += resblock(block_in, block_out)
            block_in = block_out
        if index < 3:
            encoder += conv(block_in, block_in)
    encoder += 2 * resblock(512, 512) + attn(512) + 2 * 512 + conv(512, 64)
    decoder = conv(32, 32, 1) + conv(32, 512) + 2 * resblock(512, 512) + attn(512)
    block_in = 512
    for index in reversed(range(4)):
        for _ in range(3):
            decoder += resblock(block_in, levels[index])
            block_in = levels[index]
        if index > 0:
            decoder += conv(block_in, block_in)
    decoder += 2 * 128 + conv(128, 3)
    vae_count = encoder + decoder
    # BatchNorm affine=False contributes 128 running means, 128 running vars,
    # one int64 batch counter; these are buffers, not trainable parameters.
    output = {
        "main_transformer": {"parameters": main_count, "parts": main_parts, "verification": "matches frozen HF safetensors API total"},
        "text_encoder": {"parameters": text_count, "per_layer": per_layer, "verification": "matches frozen sharded index total_parameters", "tied_embedding_counted_once": True},
        "vae": {"parameters": vae_count, "encoder": encoder, "decoder": decoder, "nontrainable_buffer_elements": 257,
                "verification": "formula derived from frozen BFL autoencoder.py; weights not loaded; not a tensor-header count"},
        "pipeline_trainable_parameters": main_count + text_count + vae_count,
        "bf16_weight_only_bytes": {"main_transformer": main_count * 2, "main_plus_text": (main_count + text_count) * 2,
                                   "all_bf16_hypothetical": (main_count + text_count + vae_count) * 2},
        "memory_warning": "Parameter bytes omit activation/KV/scratch/allocator and do not prescribe residency. Official BFL reference loads Qwen3-4B-FP8; HF pipeline text config/index are BF16; VAE upcast stages exist.",
    }
    (ROOT / "parameter_counts.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
