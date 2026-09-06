"""Independent R8 source, interval, numeric, and event recheck; never imports main runner."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "r8/results"
K, N = 9216, 128


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_digest(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def same_bits(a, b):
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def bf16_independent(raw):
    # frexp + ties-to-even rint independently implements BF16 normal-number rounding.
    # All supplied operands are finite normal numbers; this is not a general BF16 codec.
    source = np.asarray(raw, dtype=np.float32)
    mantissa, exponent = np.frexp(source.astype(np.float64))
    rounded = np.ldexp(np.rint(mantissa * 256), exponent - 8).astype(np.float32)
    return (rounded.view(np.uint32) >> 16).astype(np.uint16)


def overlaps(left, right):
    return max(left[0], right[0]) < min(left[1], right[1])


def verify_ledger():
    source = read("resource_payload_ledger.json")
    for item in source["sources"]:
        assert digest(ROOT / item["local_path"]) == item["sha256"]
    cfg = json.loads((ROOT / "r4/sources/qwen/config.json").read_text(encoding="utf8"))["text_config"]
    assert (cfg["intermediate_size"], cfg["hidden_size"], cfg["dtype"]) == (9216, 2560, "bfloat16")
    implementation = ast.parse((ROOT / "r4/sources/qwen/modeling_qwen3_5.py").read_text(encoding="utf8"))
    mlp = next(node for node in implementation.body if isinstance(node, ast.ClassDef) and node.name == "Qwen3_5MLP")
    down = next(node.value for node in ast.walk(mlp) if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Attribute) and t.attr == "down_proj" for t in node.targets))
    assert [ast.unparse(arg) for arg in down.args] == ["self.intermediate_size", "self.hidden_size"]
    assert any(k.arg == "bias" and isinstance(k.value, ast.Constant) and k.value.value is False for k in down.keywords)
    header = json.loads((ROOT / "r5/sources/qwen/representative_weight_shapes.json").read_text(encoding="utf8"))
    assert header["model.language_model.layers.0.mlp.down_proj.weight"]["shape"] == [2560, 9216]
    cases = source["cases"]
    assert {(c["mapping"], c["M"]) for c in cases} == set(itertools.product(("C1N", "C2N", "C2K"), (1, 32)))
    layout_count, core_count, details = 0, 0, []
    for case in cases:
        m, mapping, cores = case["M"], case["mapping"], case["cores"]
        expected_cores = 2 if mapping == "C1N" else 4
        assert len(cores) == expected_cores
        assert case["K"] == K and case["N"] == N
        assert case["target_timing"] is None and "pending" in case["native_admission"]
        assert sum((c["K"][1]-c["K"][0])*(c["N"][1]-c["N"][0]) for c in cores) == K*N
        for left, right in itertools.combinations(cores, 2):
            assert not (overlaps(left["K"], right["K"]) and overlaps(left["N"], right["N"]))
        for c in cores:
            core_count += 1
            kr, nr = c["K"], c["N"]
            nk, nn = kr[1] - kr[0], nr[1] - nr[0]
            assert 0 <= kr[0] < kr[1] <= K and 0 <= nr[0] < nr[1] <= N
            assert c["logical_MACs"] == m*nk*nn
            assert (c["X_bytes"], c["W_bytes"], c["P_bytes"]) == (m*nk*2, nk*nn*2, m*nn*4)
            receiving = mapping == "C2K" and c["cluster"] == 0
            expected_names = {"X", "W", "P"} | ({"incoming_P1"} if receiving else set())
            assert {b["name"] for b in c["full_resident"]["buffers"]} == expected_names
            assert {(t["Ktile"], t["buffer_count"]) for t in c["tiled"]} == set(itertools.product((128,512),(1,2)))
            for layout in [c["full_resident"], *c["tiled"]]:
                layout_count += 1
                tiled = "Ktile" in layout
                if tiled:
                    tile, count = layout["Ktile"], layout["buffer_count"]
                    assert nk % tile == 0 and layout["K_tiles"] == nk//tile
                    expected_size = count*(m*tile*2 + tile*nn*2) + m*nn*4*(2 if receiving else 1)
                else:
                    expected_size = m*nk*2 + nk*nn*2 + m*nn*4*(2 if receiving else 1)
                assert layout["live_set_bytes"] == expected_size <= 4*1024*1024
                buffers = layout["buffers"]
                assert sum(b["span_bytes"] for b in buffers) == expected_size
                for b in buffers:
                    assert b["base_bytes"] >= 0 and b["span_bytes"] > 0 and b["lifetime_end"]
                    assert b["base_bytes"]+b["span_bytes"] <= expected_size
                    expected = m*nn*4
                    if b["name"].startswith("X"):
                        expected = m*(tile if tiled else nk)*2
                    elif b["name"].startswith("W"):
                        expected = (tile if tiled else nk)*nn*2
                    assert b["span_bytes"] == expected
                for a,b in itertools.combinations(buffers,2):
                    assert not overlaps((a["base_bytes"],a["base_bytes"]+a["span_bytes"]),
                                        (b["base_bytes"],b["base_bytes"]+b["span_bytes"]))
        transfers = case["transfers"]
        outputs = [t for t in transfers if t["destination"] == "external.Y"]
        assert sum(t["payload"]["N"][1]-t["payload"]["N"][0] for t in outputs) == N
        for a,b in itertools.combinations(outputs,2):
            assert not overlaps(a["payload"]["N"],b["payload"]["N"])
        assert all(t["payload"]["M"] == [0,m] and t["emits"].endswith(".Y.external_visible") for t in outputs)
        a = case["accounting"]
        x = m*K*2*(4 if mapping == "C2N" else 2)
        partial = m*N*4 if mapping == "C2K" else 0
        expected = {"logical_MACs":m*K*N,"additional_reduction_adds":m*N if partial else 0,
                    "weight_ingress_bytes":K*N*2,"private_X_delivery_bytes":x,
                    "unique_X_external_read_lower_bound_bytes":m*K*2,"final_Y_write_bytes":m*N*4,
                    "peer_partial_bytes_direct":partial,"external_bytes_private_unicast_direct":K*N*2+x+m*N*4,
                    "external_bytes_private_unicast_staged":K*N*2+x+m*N*4+2*partial,
                    "external_partial_stage_live_bytes":partial,"reduction_local_read_bytes":2*partial,
                    "reduction_local_write_bytes":partial}
        assert a == expected
        assert sum(t["bytes"] for t in transfers if t["source"] == "external.X") == x
        assert sum(t["bytes"] for t in transfers if t["source"] == "external.W") == K*N*2
        assert sum(t["bytes"] for t in outputs) == m*N*4
        assert sum(t["bytes"] for t in transfers if t["id"].endswith(".partial")) == partial
        details.append({"mapping":mapping,"M":m,"verified_accounting":a})
    return {"cases":len(cases),"cores":core_count,"layouts":layout_count,"details":details}


def verify_numbers():
    numbers = read("numerical_results.json")
    records = numbers["random_fixtures"]
    assert len(records) == 18
    verified, max_reference_disagreement = [], 0.0
    for m,seed in itertools.product((1,32),(8107,8119,8131)):
        with np.load(OUT/f"fixture_M{m}_seed{seed}.npz",allow_pickle=False) as fixture:
            rng = np.random.default_rng(seed)
            for key,raw in [("X_bf16_bits",rng.uniform(-0.25,0.25,(m,K))),
                            ("W_bf16_bits",rng.uniform(-0.125,0.125,(K,N)))]:
                assert same_bits(fixture[key],bf16_independent(raw))
                assert np.all(fixture[key] & 0x7fff != 0)
            x = (fixture["X_bf16_bits"].astype(np.uint32)<<16).view(np.float32)
            w = (fixture["W_bf16_bits"].astype(np.uint32)<<16).view(np.float32)
            serial,split,oracle = [],[],[]
            # Cumulative sum of materialized exact BF16 products is independent from the runner's out += loop.
            for row in x:
                product = row[:,None]*w
                serial.append(np.cumsum(product,axis=0,dtype=np.float32)[-1])
                left = np.cumsum(product[:K//2],axis=0,dtype=np.float32)[-1]
                right = np.cumsum(product[K//2:],axis=0,dtype=np.float32)[-1]
                split.append(left+right)
                oracle.append(np.sum(product.astype(np.float64),axis=0,dtype=np.float64))
            serial,split,oracle = np.stack(serial),np.stack(split),np.stack(oracle)
            assert same_bits(fixture["ordered_fp32"],serial)
            discrepancy = float(np.max(np.abs(oracle-fixture["reference_fp64"])))
            max_reference_disagreement = max(max_reference_disagreement,discrepancy)
            assert discrepancy < 1e-12
            for mapping in ("C1N","C2N","C2K"):
                record = next(r for r in records if (r["M"],r["seed"],r["mapping"]) == (m,seed,mapping))
                y = fixture[mapping]
                assert same_bits(y,split if mapping == "C2K" else serial)
                assert array_digest(fixture["X_bf16_bits"]) == record["X_bf16_sha256"]
                assert array_digest(fixture["W_bf16_bits"]) == record["W_bf16_sha256"]
                assert array_digest(y) == record["output_sha256"]
                err = np.abs(y.astype(np.float64)-fixture["reference_fp64"])
                assert float(err.max()) == record["max_abs_error_fp64"]
                assert bool(np.all(err <= 5e-5+5e-5*np.abs(fixture["reference_fp64"]))) == record["diagnostic_tolerance_pass"]
                assert same_bits(y,serial) == record["bitwise_equal_ordered_fp32"]
                assert int(np.count_nonzero(y.view(np.uint32)!=serial.view(np.uint32))) == record["different_elements_ordered_fp32"]
                verified.append({"M":m,"seed":seed,"mapping":mapping,"different_from_serial":record["different_elements_ordered_fp32"]})
    witness = numbers["cancellation_witness"]
    terms = np.zeros(K,dtype=np.float32)
    terms[witness["nonzero_W_indices"]] = witness["nonzero_W_values"]
    assert np.all(terms.view(np.uint32) & 0xffff == 0)
    serial = float(np.cumsum(terms,dtype=np.float32)[-1])
    split = float(np.cumsum(terms[:K//2],dtype=np.float32)[-1]+np.cumsum(terms[K//2:],dtype=np.float32)[-1])
    exact = float(np.sum(terms,dtype=np.float64))
    assert (serial,split,exact) == (witness["ordered_fp32"],witness["split_fp32"],witness["fp64"]) == (1.0,0.0,2.0)
    return {"fixtures":6,"comparisons":len(verified),"max_reference_disagreement":max_reference_disagreement,
            "details":verified,"cancellation":{"ordered":serial,"split":split,"fp64":exact}}


def verify_events():
    # Independent recurrence uses a symbolic generation, with value decoding only at the end.
    variants = {
        "safe": "AR RV EC VE RS CD",
        "early_event": "AR RV EC AE RS CD",
        "early_source_reuse": "AR RV EC VE AS CD",
        "early_destination_reuse": "AR RV EC VE RS VD",
        "conservative_source_release": "AR RV EC VE VS CD",
    }
    observed = [json.loads(line) for line in (OUT/"event_extensions.jsonl").read_text().splitlines()]
    assert len(observed) == 70
    assert all(count == 1 for count in Counter((r["variant"],tuple(r["order"])) for r in observed).values())
    saved = read("causality_results.json")
    assert saved["total_extensions"] == 70
    details = {}
    for name,description in variants.items():
        relations = [tuple(edge) for edge in description.split()]
        expected = {}
        for events in itertools.permutations("ACDERSV"):
            if any(events.index(left)>events.index(right) for left,right in relations):
                continue
            source,destination,flight,read_value = "original","unwritten",None,None
            for event in events:
                if event == "S": source = "source_reused"
                elif event == "R": flight = source
                elif event == "V": destination = flight
                elif event == "D": destination = "destination_reused"
                elif event == "C": read_value = destination
            value = {"original":11,"unwritten":-7,"source_reused":97,"destination_reused":53}[read_value]
            expected[events] = value
        actual = {tuple(r["order"]):r for r in observed if r["variant"] == name}
        assert actual.keys() == expected.keys()
        for order,value in expected.items():
            assert actual[order]["observed"] == value
            assert actual[order]["correct"] == (value == 11)
        wrong = {order:value for order,value in expected.items() if value != 11}
        s = saved["variants"][name]
        assert set(map(tuple,s["edges"])) == set(relations)
        assert (s["linear_extensions"],s["incorrect_extensions"]) == (len(expected),len(wrong))
        if wrong:
            witness = s["first_bad_witness"]
            assert witness["variant"] == name and tuple(witness["order"]) in wrong
            assert wrong[tuple(witness["order"])] == witness["observed"] and not witness["correct"]
        else:
            assert s["first_bad_witness"] is None
        details[name] = {"extensions":len(expected),"incorrect":len(wrong),
                         "independent_witness": {"order":list(next(iter(wrong))),"observed":next(iter(wrong.values()))} if wrong else None}
    assert sum(d["incorrect"] for d in details.values()) == 37
    return {"extensions":70,"incorrect":37,"every_record_reexecuted":True,"details":details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        help="Write a new receipt to this explicit path; default only rechecks and prints PASS")
    args = parser.parse_args()
    receipt = read("receipt.json")
    assert receipt["status"] == "PASS"
    for path,value in receipt["inputs_sha256"].items():
        assert digest(ROOT/path) == value
    for name,value in receipt["artifact_sha256"].items():
        assert digest(OUT/name) == value
    checks = {"source_ledger":verify_ledger(),"numerics":verify_numbers(),"events":verify_events()}
    report = {"status":"PASS","checked_utc":datetime.now(timezone.utc).isoformat(),
              "independent_checker_sha256":digest(Path(__file__)),"main_receipt_sha256":digest(OUT/"receipt.json"),
              "evidence_level":"independent CPU and finite contract recheck only; no target admission, timing or mechanism acceptance",
              "checks":checks}
    if args.output is not None:
        args.output.resolve().write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"status":report["status"],"ledger_cases":checks["source_ledger"]["cases"],
                      "layouts":checks["source_ledger"]["layouts"],"numeric_comparisons":checks["numerics"]["comparisons"],
                      "event_extensions":checks["events"]["extensions"],"incorrect_extensions":37}))


if __name__ == "__main__":
    main()
