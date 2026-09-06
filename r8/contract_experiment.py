"""Source-bounded R8 accounting and finite causality checks. No timing model."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import platform

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "r8"
K, N = 9216, 128
SEEDS = (8107, 8119, 8131)
MAPS = ("C1N", "C2N", "C2K")
STORAGE_LIMIT = 4 * 1024 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ahash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf8")


def verify_sources():
    spec = json.loads((ROOT / "r5/full_width_specs.json").read_text(encoding="utf8"))
    records = [f for f in spec["source_files"] if f["local_path"].startswith("r4/sources/qwen/")]
    for entry in records:
        assert sha(ROOT / entry["local_path"]) == entry["sha256"], entry
    config = json.loads((ROOT / "r4/sources/qwen/config.json").read_text(encoding="utf8"))["text_config"]
    assert config["intermediate_size"] == K and config["hidden_size"] == 2560
    assert config["dtype"] == "bfloat16"
    return records


def shards(mapping):
    clusters = 1 if mapping == "C1N" else 2
    result = []
    for cluster in range(clusters):
        for core in range(2):
            if mapping == "C2K":
                kr = [cluster * (K // 2), (cluster + 1) * (K // 2)]
                nr = [core * (N // 2), (core + 1) * (N // 2)]
            else:
                kr = [0, K]
                width = N // (clusters * 2)
                index = cluster * 2 + core
                nr = [index * width, (index + 1) * width]
            result.append({"cluster": cluster, "core": core, "K": kr, "N": nr})
    return result


def allocate(parts):
    offset, buffers = 0, []
    for name, size, last_reader in parts:
        buffers.append({"name": name, "base_bytes": offset, "span_bytes": size,
                        "lifetime_end": last_reader})
        offset += size
    assert offset <= STORAGE_LIMIT
    return {"buffers": buffers, "live_set_bytes": offset,
            "capacity_check": "fits research 4MiB bound; target reserved regions/banks not admitted"}


def ledger(mapping, m):
    ss = shards(mapping)
    cover = np.zeros((K, N), dtype=np.uint8)
    all_cores, transfers = [], []
    for s in ss:
        ka, kb = s["K"]
        na, nb = s["N"]
        cover[ka:kb, na:nb] += 1
        nk, nn = kb - ka, nb - na
        xbytes, wbytes, pbytes = m * nk * 2, nk * nn * 2, m * nn * 4
        owner = f"c{s['cluster']}.k{s['core']}"
        receive = mapping == "C2K" and s["cluster"] == 0
        # The in-place reduction overwrites local P only after both P operands are readable.
        parts = [("X", xbytes, "projection.last_read"),
                 ("W", wbytes, "projection.last_read"),
                 ("P", pbytes, "output_store.last_read" if receive or mapping != "C2K"
                  else "partial_transfer.source_last_read")]
        if receive:
            parts.append(("incoming_P1", pbytes, "reduction.last_read"))
        resident = allocate(parts)
        tiled = []
        for kt in (128, 512):
            for count in (1, 2):
                tile_parts = []
                for slot in range(count):
                    tile_parts.extend([(f"X{slot}", m * kt * 2, "tile.last_read before refill"),
                                       (f"W{slot}", kt * nn * 2, "tile.last_read before refill")])
                tile_parts.append(("P", pbytes, parts[2][2]))
                if receive:
                    tile_parts.append(("incoming_P1", pbytes, "reduction.last_read"))
                tiled.append({"Ktile": kt, "buffer_count": count,
                              "K_tiles": nk // kt, **allocate(tile_parts)})
        all_cores.append({**s, "owner": owner, "logical_MACs": m * nk * nn,
                          "X_bytes": xbytes, "W_bytes": wbytes, "P_bytes": pbytes,
                          "full_resident": resident, "tiled": tiled})
        transfers += [
            {"id": owner + ".X", "source": "external.X", "destination": owner + ".X",
             "bytes": xbytes, "payload": {"M": [0, m], "K": s["K"]},
             "requires": "external.X.visible", "emits": owner + ".X.visible"},
            {"id": owner + ".W", "source": "external.W", "destination": owner + ".W",
             "bytes": wbytes, "payload": {"K": s["K"], "N": s["N"]},
             "requires": "external.W.visible", "emits": owner + ".W.visible"}]
        if mapping == "C2K" and s["cluster"] == 1:
            target = f"c0.k{s['core']}.incoming_P1"
            transfers.append({"id": owner + ".partial", "source": owner + ".P", "destination": target,
                              "bytes": pbytes, "payload": {"M": [0, m], "N": s["N"]},
                              "requires": owner + ".P.local_visible", "emits": target + ".visible",
                              "route_alternatives": ["direct_peer", "external_stage_write_then_read"],
                              "source_reuse_after": owner + ".partial.source_last_read",
                              "destination_reuse_after": f"c0.k{s['core']}.reduction.last_read"})
        else:
            transfers.append({"id": owner + ".Y", "source": owner + ".P", "destination": "external.Y",
                              "bytes": pbytes, "payload": {"M": [0, m], "N": s["N"]},
                              "requires": owner + (".reduction.visible" if receive else ".P.local_visible"),
                              "emits": owner + ".Y.external_visible"})
    assert np.all(cover == 1), "missing or repeated MAC/weight element"
    xb = sum(c["X_bytes"] for c in all_cores)
    wb = sum(c["W_bytes"] for c in all_cores)
    peer = m * N * 4 if mapping == "C2K" else 0
    output = m * N * 4
    assert wb == K * N * 2
    assert sum(t["bytes"] for t in transfers if t["id"].endswith(".Y")) == output
    dependencies = []
    for c in all_cores:
        p = c["owner"]
        dependencies.append({"operation": p + ".projection", "waits": [p + ".X.visible", p + ".W.visible"],
                             "emits": p + ".P.local_visible", "reduction_order": "K ascending"})
        if mapping == "C2K" and c["cluster"] == 0:
            dependencies.append({"operation": p + ".reduction", "waits": [p + ".P.local_visible", p + ".incoming_P1.visible"],
                                 "emits": p + ".reduction.visible", "arithmetic": "P0 + P1 in FP32, in-place P0"})
    return {"mapping": mapping, "M": m, "K": K, "N": N, "cores": all_cores,
            "transfers": transfers, "strict_dependencies": dependencies,
            "final_completion": "all disjoint Y stores external-visible",
            "accounting": {"logical_MACs": m * K * N, "additional_reduction_adds": m * N if peer else 0,
                           "weight_ingress_bytes": wb, "private_X_delivery_bytes": xb,
                           "unique_X_external_read_lower_bound_bytes": m * K * 2,
                           "final_Y_write_bytes": output, "peer_partial_bytes_direct": peer,
                           "external_bytes_private_unicast_direct": wb + xb + output,
                           "external_bytes_private_unicast_staged": wb + xb + output + 2 * peer,
                           "external_partial_stage_live_bytes": peer,
                           "reduction_local_read_bytes": 2 * output if peer else 0,
                           "reduction_local_write_bytes": output if peer else 0},
            "native_admission": "pending; M1 violates historical 32-multiple MXU geometry" if m == 1
            else "pending; historical geometry only, no dtype/RTL/compiler admission",
            "target_timing": None}


def bf16(array):
    bits = np.asarray(array, dtype=np.float32).view(np.uint32)
    rounded = bits + np.uint32(0x7FFF) + ((bits >> 16) & 1)
    return (rounded & np.uint32(0xFFFF0000)).view(np.float32)


def ordered_dot(x, w):
    out = np.zeros((x.shape[0], w.shape[1]), dtype=np.float32)
    for i in range(x.shape[1]):
        np.add(out, x[:, i:i+1] * w[i:i+1, :], out=out)
    return out


def execute_mapping(x, w, mapping):
    partials = []
    for s in shards(mapping):
        ka, kb = s["K"]
        na, nb = s["N"]
        partials.append(ordered_dot(x[:, ka:kb], w[ka:kb, na:nb]))
    if mapping == "C2K":
        return np.concatenate([partials[0] + partials[2], partials[1] + partials[3]], axis=1)
    return np.concatenate(partials, axis=1)


def numerical(outdir):
    records = []
    for m, seed in itertools.product((1, 32), SEEDS):
        rng = np.random.default_rng(seed)
        x = bf16(rng.uniform(-0.25, 0.25, (m, K)))
        w = bf16(rng.uniform(-0.125, 0.125, (K, N)))
        ref64 = x.astype(np.float64) @ w.astype(np.float64)
        baseline = ordered_dot(x, w)
        arrays = {"X_bf16_bits": (x.view(np.uint32) >> 16).astype(np.uint16),
                  "W_bf16_bits": (w.view(np.uint32) >> 16).astype(np.uint16),
                  "reference_fp64": ref64, "ordered_fp32": baseline}
        for mapping in MAPS:
            y = execute_mapping(x, w, mapping)
            err = np.abs(y.astype(np.float64) - ref64)
            passed = bool(np.all(err <= 5e-5 + 5e-5 * np.abs(ref64)))
            equal = bool(np.array_equal(y, baseline))
            records.append({"M": m, "seed": seed, "mapping": mapping,
                            "X_bf16_sha256": ahash(arrays["X_bf16_bits"]),
                            "W_bf16_sha256": ahash(arrays["W_bf16_bits"]), "output_sha256": ahash(y),
                            "max_abs_error_fp64": float(err.max()), "diagnostic_tolerance_pass": passed,
                            "bitwise_equal_ordered_fp32": equal,
                            "different_elements_ordered_fp32": int(np.count_nonzero(y != baseline))})
            assert passed, records[-1]
            if mapping != "C2K":
                assert equal, records[-1]
            arrays[mapping] = y
        np.savez_compressed(outdir / f"fixture_M{m}_seed{seed}.npz", **arrays)
    # Explicit counterexample to unlicensed reassociation. BF16 products, FP32 add.
    x = np.ones((1, K), dtype=np.float32)
    w = np.zeros((K, 1), dtype=np.float32)
    big = bf16(np.array([1e8], dtype=np.float32))[0]
    w[0, 0], w[1, 0], w[K // 2, 0], w[K // 2 + 1, 0] = big, 1, -big, 1
    serial = ordered_dot(x, w)[0, 0]
    split = (ordered_dot(x[:, :K//2], w[:K//2]) + ordered_dot(x[:, K//2:], w[K//2:]))[0, 0]
    exact = (x.astype(np.float64) @ w.astype(np.float64))[0, 0]
    assert serial != split
    return {"random_fixtures": records, "cancellation_witness": {"K": K, "BF16_big": float(big),
            "nonzero_W_indices": [0, 1, K//2, K//2+1], "nonzero_W_values": [float(big), 1, -float(big), 1],
            "ordered_fp32": float(serial), "split_fp32": float(split), "fp64": float(exact),
            "verdict": "reject bitwise-equivalence inference; target numerical license still required"}}


def causality(outdir):
    # R captures a single sentinel word. No real network/protocol capacity claim.
    base = [("A", "R"), ("R", "V"), ("E", "C")]
    variants = {
        "safe": [("V", "E"), ("R", "S"), ("C", "D")],
        "early_event": [("A", "E"), ("R", "S"), ("C", "D")],
        "early_source_reuse": [("V", "E"), ("A", "S"), ("C", "D")],
        "early_destination_reuse": [("V", "E"), ("R", "S"), ("V", "D")],
        "conservative_source_release": [("V", "E"), ("V", "S"), ("C", "D")],
    }
    summary, traces = {}, []
    for name, extra in variants.items():
        edges, cases = base + extra, []
        for order in itertools.permutations("ARVE CSD".replace(" ", "")):
            pos = {event: i for i, event in enumerate(order)}
            if not all(pos[a] < pos[b] for a, b in edges):
                continue
            src, transport, dst, observed = 11, None, -7, None
            for event in order:
                if event == "R":
                    transport = src
                elif event == "V":
                    dst = transport
                elif event == "S":
                    src = 97
                elif event == "D":
                    dst = 53
                elif event == "C":
                    observed = dst
            case = {"variant": name, "order": list(order), "observed": observed, "correct": observed == 11}
            cases.append(case)
        bad = [c for c in cases if not c["correct"]]
        summary[name] = {"edges": edges, "linear_extensions": len(cases), "incorrect_extensions": len(bad),
                         "first_bad_witness": bad[0] if bad else None}
        traces.extend(cases)
        assert cases
        assert not bad if name in ("safe", "conservative_source_release") else bool(bad)
    with (outdir / "event_extensions.jsonl").open("w", encoding="utf8") as stream:
        for record in traces:
            stream.write(json.dumps(record) + "\n")
    return {"scope": "all linear extensions of five declared seven-event partial orders; no probabilities or timing",
            "variants": summary, "total_extensions": len(traces)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "results")
    args = parser.parse_args()
    outdir = args.output.resolve()
    # Results are immutable runs; reruns require a new directory.
    outdir.mkdir(parents=True, exist_ok=False)
    start = datetime.now(timezone.utc).isoformat()
    provenance = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in
                  (HERE / "experiment_plan.md", HERE / "prerun_clarifications.md", Path(__file__))}
    receipt = {"started_utc": start, "evidence_level": "CPU fixture + exact finite structural checks; no target timing",
               "inputs_sha256": provenance, "python": platform.python_version(), "numpy": np.__version__}
    write(outdir / "receipt.json", {**receipt, "status": "started"})
    try:
        sources = verify_sources()
        entries = [ledger(mapping, m) for m, mapping in itertools.product((1, 32), MAPS)]
        write(outdir / "resource_payload_ledger.json", {"sources": sources, "cases": entries})
        numbers = numerical(outdir)
        write(outdir / "numerical_results.json", numbers)
        events = causality(outdir)
        write(outdir / "causality_results.json", events)
        artifact_hashes = {p.name: sha(p) for p in sorted(outdir.iterdir()) if p.name != "receipt.json"}
        write(outdir / "receipt.json", {**receipt, "status": "PASS", "finished_utc": datetime.now(timezone.utc).isoformat(),
                                        "artifact_sha256": artifact_hashes})
        print(json.dumps({"status": "PASS", "ledger_cases": len(entries), "numeric_comparisons": len(numbers["random_fixtures"]),
                          "causality": events, "output": str(outdir)}, ensure_ascii=False))
    except Exception as exc:
        write(outdir / "receipt.json", {**receipt, "status": "FAIL", "error": repr(exc),
                                        "finished_utc": datetime.now(timezone.utc).isoformat()})
        raise


if __name__ == "__main__":
    main()
