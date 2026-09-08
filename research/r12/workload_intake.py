"""Audit frozen Qwen MLP sources and derive logical full-module work, using stdlib.

No weights, model imports, numeric kernel, performance model, or device execution.
Pinned Git contents are the authority. Historical source artifacts used mixed LF
and CRLF: the declared archive encoding is checked against the frozen manifest,
while working-tree byte hashes are reported separately, never called equal.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path


PROJECT_REVISION = "a947b563356610cf4dbb05995debf18fc3054e66"
MODEL_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
TRANSFORMERS_REVISION = "f62dc9bf2c90353b442a56e74391fbb8c689b55e"
SOURCE_BASE = "research/r5/sources/"
MANIFEST_PATH = SOURCE_BASE + "resource_source_manifest.json"
# This is an explicit record of the frozen artifacts' byte representation,
# established by checking pinned blobs and the original manifest. Not a search
# for arbitrary normalizations that happen to produce a passing hash.
ARCHIVE_EOL = {
    "qwen/config.json": "LF",
    "qwen/modeling_qwen3_5.py": "LF",
    "qwen/representative_weight_shapes.json": "CRLF",
    "qwen/r4_manifest.json": "CRLF",
}
EXPECTED_SHA256 = {
    "qwen/config.json": "ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670",
    "qwen/modeling_qwen3_5.py": "458360c8072e6130580639170ad3e645b975512dbabae31eab5f92de5f0f09ef",
    "qwen/representative_weight_shapes.json": "0cfea86881cb17b746b5b8150bf7ce35605756141c1ab365b1c4df9e962d372a",
    "qwen/r4_manifest.json": "cc49171e4ad054b04372299c06e1a441f8f5792b652a4e25789f791fdfd8a05e",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(root: Path, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{PROJECT_REVISION}:{path}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    require(result.returncode == 0, f"Cannot read pinned Git source: {path}")
    return result.stdout


def audit_sources(root: Path) -> tuple[dict, dict[str, bytes]]:
    manifest_raw = git_blob(root, MANIFEST_PATH)
    manifest = json.loads(manifest_raw)
    entries = {item["path"]: item for item in manifest["files"]}
    evidence = []
    contents = {}
    for relative, eol in ARCHIVE_EOL.items():
        path = SOURCE_BASE + relative
        canonical = git_blob(root, path)
        require(b"\r" not in canonical, f"Pinned blob is no longer LF-only: {path}")
        archived = canonical if eol == "LF" else canonical.replace(b"\n", b"\r\n")
        expected = entries[relative]
        require(expected["sha256"] == EXPECTED_SHA256[relative], f"Manifest drift: {path}")
        require(sha256(archived) == expected["sha256"], f"Frozen source hash mismatch: {path}")
        require(len(archived) == expected["bytes"], f"Frozen source byte count mismatch: {path}")
        working = (root / path).read_bytes()
        require(
            working.replace(b"\r\n", b"\n") == canonical,
            f"Working source has a change beyond checkout line endings: {path}",
        )
        evidence.append({
            "path": path,
            "manifest_sha256": expected["sha256"],
            "manifest_bytes": expected["bytes"],
            "declared_archive_eol": eol,
            "reconstructed_archive_sha256": sha256(archived),
            "reconstructed_archive_exact_match": True,
            "pinned_git_blob_sha256": sha256(canonical),
            "pinned_git_blob_bytes": len(canonical),
            "working_tree_sha256": sha256(working),
            "working_tree_bytes": len(working),
            "working_tree_raw_manifest_match": sha256(working) == expected["sha256"],
            "working_tree_matches_pinned_content_after_explicit_crlf_to_lf": True,
        })
        contents[relative] = canonical
    provenance = json.loads(contents["qwen/r4_manifest.json"])
    require(provenance["model_repo"] == "Qwen/Qwen3.5-4B", "Model identity mismatch")
    require(provenance["model_revision"] == MODEL_REVISION, "Model revision mismatch")
    require(provenance["transformers_revision"] == TRANSFORMERS_REVISION, "Transformers revision mismatch")
    origin_entries = {item["file"]: item for item in provenance["files"]}
    for name in ("config.json", "modeling_qwen3_5.py"):
        require(
            origin_entries[name]["sha256"] == EXPECTED_SHA256["qwen/" + name],
            f"Origin/R5 manifest disagreement: {name}",
        )
    return {
        "status": "pinned_content_and_declared_archive_hashes_verified",
        "content_authority": "pinned_git_blobs",
        "project_revision": PROJECT_REVISION,
        "model_revision": MODEL_REVISION,
        "transformers_revision": TRANSFORMERS_REVISION,
        "manifest_path": MANIFEST_PATH,
        "manifest_pinned_git_sha256": sha256(manifest_raw),
        "raw_working_tree_manifest_matches": sum(e["working_tree_raw_manifest_match"] for e in evidence),
        "source_count": len(evidence),
        "files": evidence,
        "network_requests": 0,
        "weight_payloads_downloaded": False,
    }, contents


def expression(text: str) -> str:
    return ast.dump(ast.parse(text, mode="eval").body, include_attributes=False)


def audit_mlp(contents: dict[str, bytes]) -> dict:
    config = json.loads(contents["qwen/config.json"])["text_config"]
    require(config["hidden_size"] == 2560, "Unexpected H")
    require(config["intermediate_size"] == 9216, "Unexpected I")
    require(config["hidden_act"] == "silu", "Unexpected activation")
    require(config["dtype"] == "bfloat16", "Unexpected config dtype")
    module = ast.parse(contents["qwen/modeling_qwen3_5.py"].decode("utf-8"))
    mlps = [node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Qwen3_5MLP"]
    require(len(mlps) == 1, "Expected one Qwen3_5MLP definition")
    mlp = mlps[0]
    functions = {node.name: node for node in mlp.body if isinstance(node, ast.FunctionDef)}
    assignments = {
        ast.unparse(node.targets[0]): ast.dump(node.value, include_attributes=False)
        for node in functions["__init__"].body if isinstance(node, ast.Assign)
    }
    for name, args in {
        "gate_proj": "self.hidden_size, self.intermediate_size",
        "up_proj": "self.hidden_size, self.intermediate_size",
        "down_proj": "self.intermediate_size, self.hidden_size",
    }.items():
        require(assignments["self." + name] == expression(f"nn.Linear({args}, bias=False)"), f"Changed {name}")
    require(assignments["self.act_fn"] == expression("ACT2FN[config.hidden_act]"), "Changed activation dispatch")
    forward = functions["forward"]
    expected_forward = ast.parse(
        "down_proj = self.down_proj(self.act_fn(self.gate_proj(x)) * self.up_proj(x))\nreturn down_proj"
    ).body
    require(
        [ast.dump(node, include_attributes=False) for node in forward.body]
        == [ast.dump(node, include_attributes=False) for node in expected_forward],
        "Changed source MLP forward algebra",
    )
    shapes = json.loads(contents["qwen/representative_weight_shapes.json"])
    weights = []
    for projection in ("gate", "up", "down"):
        expected_shape = [2560, 9216] if projection == "down" else [9216, 2560]
        for layer in (0, 3):
            key = f"model.language_model.layers.{layer}.mlp.{projection}_proj.weight"
            record = shapes[key]
            require(record["shape"] == expected_shape, f"Changed shape: {key}")
            require(record["dtype"] == "BF16", f"Changed dtype: {key}")
            require(record["parameters"] == 2560 * 9216, f"Changed parameter count: {key}")
        weights.append({
            "tensor": f"W_{projection}", "shape_out_in": expected_shape,
            "parameters": 2560 * 9216, "storage_dtype": "BF16", "bytes": 2560 * 9216 * 2,
        })
    return {
        "H": 2560, "I": 9216, "M": [1, 32, 128],
        "module": "one complete dense MLP; not a complete decoder layer or model",
        "algebra": "down(SiLU(gate(X))*up(X))",
        "source_class_lines": [mlp.lineno, mlp.end_lineno],
        "bias": False, "weights": weights,
        "total_parameters": sum(w["parameters"] for w in weights),
        "total_bf16_weight_bytes": sum(w["bytes"] for w in weights),
        "activation_storage_dtype": "pending native numerical contract; byte alternatives listed below",
    }


def derive_workload(mlp: dict, m: int) -> dict:
    h, i = mlp["H"], mlp["I"]
    tensors = []
    for name, columns, producer, readers in (
        ("X", h, "module_input", ["gate", "up"]),
        ("G", i, "gate", ["silu"]),
        ("U", i, "up", ["multiply"]),
        ("S", i, "silu", ["multiply"]),
        ("A", i, "multiply", ["down"]),
        ("Y", h, "down", ["module_output"]),
    ):
        tensors.append({
            "tensor": name, "shape": [m, columns], "elements": m * columns,
            "bytes_if_bf16": m * columns * 2, "bytes_if_fp32": m * columns * 4,
            "producer": producer, "all_logical_readers": readers,
        })
    per_projection = {name: m * weight["parameters"] for name, weight in zip(("gate", "up", "down"), mlp["weights"])}
    total_macs = sum(per_projection.values())
    require(total_macs == 3 * m * h * i, "Projection MAC sum is inconsistent")
    return {
        "M": m,
        "input_availability": "one current request only; no future-token input" if m == 1 else "all M input rows exist at module entry; prefill",
        "logical_tensors": tensors,
        "logical_macs_by_projection": per_projection,
        "logical_macs_total": total_macs,
        "gemm_flops_if_mac_counted_as_two": 2 * total_macs,
        "silu_evaluations": m * i,
        "elementwise_gate_up_multiplies": m * i,
        "pointwise_kernel_instruction_count": None,
        "native_padded_macs": None,
        "conditional_cold_bf16_boundary_payload_bytes": mlp["total_bf16_weight_bytes"] + 4 * m * h,
        "boundary_payload_condition": "one copy of each W and BF16 X read from shared DRAM, BF16 Y written to shared DRAM exactly once; excludes all additional movement",
        "actual_external_bytes": None,
        "actual_noc_bytes": None,
        "peak_sram_bytes": None,
        "elapsed": None,
        "numerical_admission": "not_run",
    }


def build_intake(root: Path) -> dict:
    source_audit, contents = audit_sources(root)
    mlp = audit_mlp(contents)
    return {
        "schema": "r12.workload-intake.v1",
        "status": "source_and_logical_work_accepted_native_admission_pending",
        "evidence_level": "local pinned-source/AST/hash checks and exact integer arithmetic",
        "source_audit": source_audit,
        "mlp": mlp,
        "configurations": [derive_workload(mlp, m) for m in mlp["M"]],
        "native_admission_gaps": [
            {"id": "hardware", "status": "pending", "required": "board/SKU, firmware, tt-metal revision, SoC descriptor and harvest mask"},
            {"id": "numerics", "status": "pending", "required": "BF16/FP32 math fidelity, accumulator/export/cast rounding, SiLU approximation and explicit reduction tree; compare full output with independent FP64 source algebra"},
            {"id": "split_k", "status": "pending", "required": "explicit permission for reduction reassociation; R8 tolerance results are not native permission"},
            {"id": "padding", "status": "pending", "required": "M=1 legal native tiling/tail, zero-fill source, valid output mask, padded MAC/transfer counts; no imported TARS 32-multiple rule"},
            {"id": "layout_and_lifetime", "status": "pending", "required": "physical tensor tiling, bank/controller placement, addresses, sharding/replication, all readers, SRAM reserves, CB slots, fusion and spill"},
            {"id": "cold_warm", "status": "pending", "required": "freeze complete initial/final locations and cold/warm policy before performance; warm weights require capacity and lifetime evidence, no free residency"},
            {"id": "noc_events", "status": "pending", "required": "bind each transfer to acceptance, source-last-read, destination-visible and notification; all last readers must precede reuse"},
            {"id": "native_execution", "status": "pending", "required": "execute full gate/up/SiLU/multiply/down, check output and physical work/traffic; R8 down N=128 slice is ineligible as full-module metric"},
            {"id": "performance", "status": "pending", "required": "calibration and preregistered P0/P1 complete-module elapsed, timing boundary and controller/link/NIU evidence"},
        ],
        "exclusions": [
            "no weight payload download or generation",
            "no full-module numerical execution",
            "no physical padding/layout/traffic inference from logical elements",
            "tensor inventory is neither peak live memory nor memory traffic",
            "source BF16 dtype does not fix backend arithmetic semantics",
            "no performance ranking, H1/H2 result, device validation or hardware admission",
            "no historical result changes or historical performance reruns",
        ],
        "producer_script_sha256": sha256(Path(__file__).read_bytes()),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "research/r12/artifacts/workload_intake.json")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(root / "research/r12"), "Output must remain inside research/r12")
    result = build_intake(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": result["status"],
        "source_artifacts_verified": result["source_audit"]["source_count"],
        "raw_working_tree_manifest_matches": result["source_audit"]["raw_working_tree_manifest_matches"],
        "bf16_weight_bytes": result["mlp"]["total_bf16_weight_bytes"],
        "logical_macs": {str(c["M"]): c["logical_macs_total"] for c in result["configurations"]},
        "output": str(output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Workload intake rejected: {error}") from error
