"""STREAM/TETRA native static evaluation driver (analytical, not execution).

Run under the R12 virtual environment, which holds the pinned STREAM install:

    research/r12/.venv/Scripts/python.exe -X utf8 -B \
        research/infra_open_source/src/schedinfra/backend/stream_static.py \
        native-smoke --output <run_dir>

    ... stream_static.py qwen-mlp --output <run_dir> [--m 32]

What this is and is not
-----------------------
* Uses the pinned upstream checkout (commit 75748cc1...), upstream hardware
  YAML and upstream entry point ``stream.api.optimize_allocation_co_generic``.
  No upstream source is modified; the checkout is verified clean before and
  after each run.
* ``evaluation_kind = analytical_static``. The numbers are the authors' cost
  model output: solver objectives, steady-state analytical latency. They are
  NOT B1-B3 dynamic execution evidence, must not be labelled RUNTIME_READY,
  and say nothing about unmodelled credits, banks or runtime reordering.
* The Qwen MLP is brought in through STREAM's native ONNX workload input.
  What STREAM cannot represent is declared PARTIAL, never replaced with an
  identity/no-op.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

INFRA = Path(__file__).resolve().parents[3]
ROOT = INFRA.parents[1]
STREAM = ROOT / "research" / "r12" / "deps" / "stream"
STREAM_COMMIT = "75748cc17e7c43add5a7d0d8f080841eb26531c4"

# Sourced Qwen3.5-4B MLP (research/r13/numerical_contract.json)
M_PAD, H, I = 32, 2560, 9216

HARDWARE_YAML = STREAM / "stream" / "inputs" / "examples" / "hardware" / "tpu_like_quad_core.yaml"
UPSTREAM_FIXTURE = STREAM / "stream" / "inputs" / "testing" / "workload" / "2conv_1_8_32_32_16_32_3.onnx"

# Native hardware options for the Qwen MLP run. tpu_like_quad_core is the
# upstream default, but the full module's 33.84 MB resident set exceeds its
# 2 MiB/core SRAM (measured: InfeasibleAllocationError, short by 31.84 MB);
# tpu_v7_ironwood is the upstream big-chip example with 64 MiB VMEM per
# TensorCore. Both are unmodified upstream files.
QWEN_HARDWARE = {
    "tpu_like_quad_core": HARDWARE_YAML,
    "tpu_v7_ironwood": STREAM / "stream" / "inputs" / "examples" / "hardware" / "tpu_v7_ironwood.yaml",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(STREAM), *args], text=True).strip()


def require(cond: bool, message: str) -> None:
    if not cond:
        raise RuntimeError(message)


def verify_environment(result: dict) -> None:
    require(git("rev-parse", "HEAD") == STREAM_COMMIT, "STREAM checkout is not at the pinned commit")
    status = git("status", "--porcelain")
    require(not status, f"STREAM checkout is dirty: {status}")
    result["environment"] = {
        "stream_commit": STREAM_COMMIT,
        "stream_checkout": str(STREAM),
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "checkout_clean_before": True,
    }


def import_stream(result: dict):
    sys.path.insert(0, str(STREAM))
    import stream.api as api  # noqa: PLC0415

    api_path = Path(api.__file__).resolve()
    require(api_path.is_relative_to(STREAM), f"wrong stream import: {api_path}")
    from importlib.metadata import version  # noqa: PLC0415

    result["environment"]["packages"] = {
        name: version(name)
        for name in ("stream-dse", "zigzag-dse", "ortools", "pydantic", "xdsl", "numpy", "onnx")
    }
    result["environment"]["stream_api_path"] = str(api_path)
    return api


def selected_structure(context, result: dict) -> dict:
    """The solver's *selected* structure, exported for audit and comparison."""
    from stream.cost_model.communication_manager import MulticastPathPlan  # noqa: PLC0415
    from stream.ir.allocation import AllocationIR  # noqa: PLC0415
    from stream.opt.allocation.constraint_optimization.utils import (  # noqa: PLC0415
        get_transfer_latency_for_path,
    )

    scheduler = context.get("scheduler")
    allocation = AllocationIR.from_internal(scheduler)
    node_cores = {}
    for node_name, entry in allocation.mapping_nodes.items():
        cores = sorted({
            resource["id"]
            for slot in entry.resource_allocation
            for resource in slot
            if resource.get("type") == "core"
        })
        node_cores[node_name] = {
            "cores": cores,
            "inter_core_tiling": entry.inter_core_tiling,
            "memory_allocation": entry.memory_allocation,
        }
    transfers = []
    for transfer in scheduler.steady_state_workload.get_transfer_nodes():
        mapping = scheduler.mapping.get(transfer)
        for path in mapping.resource_allocation:
            if isinstance(path, MulticastPathPlan):
                transfers.append({
                    "transfer": transfer.name,
                    "tensor_bits": transfer.inputs[0].size_bits(),
                    "sources": [c.id for c in path.sources],
                    "targets": [c.id for c in path.targets],
                    "links": [str(link) for link in path.links_used],
                    "upstream_single_firing_path_cycles": get_transfer_latency_for_path(transfer, path),
                })
    solve = allocation.solve.model_dump(mode="json") if allocation.solve else None
    return {
        "node_core_allocation": node_cores,
        "transfer_paths": transfers,
        "solve": solve,
        "allocation_ir_json": allocation.model_dump_json(),
    }


def run_allocation(api, hardware: Path, workload: Path, experiment_id: str, output: Path,
                   constraint_selection, fusion_cut_points=None) -> dict:
    from stream.opt.solver import ConstraintSelection  # noqa: PLC0415

    os.chdir(STREAM)  # upstream resolves referenced YAML paths from the checkout
    api.configure_logging()
    started = time.perf_counter()
    context = api.optimize_allocation_co_generic(
        hardware=str(hardware),
        workload=str(workload),
        experiment_id=experiment_id,
        output_path=str(output),
        backend="ortools_gscip",
        constraint_selection=constraint_selection or ConstraintSelection(),
        fusion_cut_points=fusion_cut_points,
        skip_if_exists=False,
    )
    wall = time.perf_counter() - started
    structure = selected_structure(context, {})
    return {
        "experiment_id": experiment_id,
        "wall_seconds": round(wall, 3),
        "analytical_total_latency_cycles": context.get("total_latency"),
        "group_latencies": context.get("group_latencies"),
        "scheduler_iterations": context.get("scheduler").iterations,
        "selected": {k: v for k, v in structure.items() if k != "allocation_ir_json"},
        "allocation_ir_json": structure["allocation_ir_json"],
    }


# --------------------------------------------------------------------------
# native-smoke: upstream fixture, upstream hardware, upstream entry
# --------------------------------------------------------------------------
def cmd_native_smoke(args) -> int:
    output = Path(args.output).resolve()
    require(not output.exists(), f"output {output} exists; runs are never overwritten")
    output.mkdir(parents=True)
    result = {
        "schema": "schedresearch.infra.stream_static.v1",
        "run_kind": "native_smoke",
        "evaluation_kind": "analytical_static",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {
            "hardware": {"path": str(HARDWARE_YAML), "sha256": sha256(HARDWARE_YAML)},
            "workload": {"path": str(UPSTREAM_FIXTURE), "sha256": sha256(UPSTREAM_FIXTURE)},
        },
        "command": " ".join(sys.argv),
        "passed": False,
    }
    previous_cwd = Path.cwd()
    try:
        verify_environment(result)
        api = import_stream(result)
        run = run_allocation(api, HARDWARE_YAML, UPSTREAM_FIXTURE, "upstream-2conv",
                             output / "pipeline", constraint_selection=None)
        (output / "allocation_ir.json").write_text(run.pop("allocation_ir_json"), encoding="utf-8")
        result["run"] = run
        result["upstream_documented_reference_cycles"] = 14344
        result["matches_documented_reference"] = run["analytical_total_latency_cycles"] == 14344
        require(run["analytical_total_latency_cycles"] > 0, "nonpositive analytical latency")
        require(run["selected"]["solve"] is not None and run["selected"]["solve"]["status"] == "OPTIMAL",
                "TETRA did not report OPTIMAL")
        require(bool(run["selected"]["transfer_paths"]), "no transfer paths selected")
        result["passed"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = {"type": type(exc).__name__, "message": str(exc),
                           "traceback": traceback.format_exc()}
    finally:
        os.chdir(previous_cwd)
        status = git("status", "--porcelain")
        result["environment"]["checkout_clean_after"] = not status
        if status:
            result["passed"] = False
            result["source_mutation_detected"] = status
        (output / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "result": str(output / "result.json"),
                      "latency_cycles": result.get("run", {}).get("analytical_total_latency_cycles"),
                      "wall_seconds": result.get("run", {}).get("wall_seconds")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


# --------------------------------------------------------------------------
# qwen-mlp: sourced MLP in STREAM's native ONNX input
# --------------------------------------------------------------------------
def build_qwen_mlp_onnx(path: Path, m: int = M_PAD) -> dict:
    """Qwen3.5-4B MLP as ONNX with contract-exact operand bitwidths.

    x / w_gate / w_up / w_down / A16 are BFLOAT16, G / U / S / Y are FLOAT -
    exactly the dtypes of research/r13/numerical_contract.json, so footprints
    and traffic match the contract byte for byte. (Verified: STREAM's parser
    supports FLOAT and BFLOAT16 and accepts the mixed graph.)

    Declared fidelity deviations (PARTIAL), exact and deliberate:
    * The explicit FP32->BF16 cast has no STREAM parser (proven by the cast
      diagnostic) and is NOT inserted as an identity. Instead the Mul node is
      typed to output BF16 directly: bitwidth and materialisation match the
      post-cast contract, but the cast's arithmetic work (M*I conversions)
      is not charged to any node in the analytical latency.
    * Initializer VALUES are zeros: the analysis uses shapes and bitwidths
      only. Nothing numerical is claimed from these tensors.
    * The analytical model executes no arithmetic: BF16 rounding itself
      happens nowhere; numerical correctness belongs to the CPU reference
      and the plan replay, not here.
    """
    import onnx  # noqa: PLC0415
    from onnx import TensorProto, helper  # noqa: PLC0415

    def zeros(name: str, dtype: int, dims: list[int]) -> onnx.TensorProto:
        count = 1
        for d in dims:
            count *= d
        width = 2 if dtype == TensorProto.BFLOAT16 else 4
        return helper.make_tensor(name, dtype, dims, vals=bytes(width * count), raw=True)

    def vi(name: str, dtype: int, dims: list[int]) -> onnx.ValueInfoProto:
        return helper.make_tensor_value_info(name, dtype, dims)

    bf16, f32 = TensorProto.BFLOAT16, TensorProto.FLOAT
    nodes = [
        helper.make_node("Gemm", ["x", "w_gate"], ["G"], name="gemm_gate"),
        helper.make_node("Gemm", ["x", "w_up"], ["U"], name="gemm_up"),
        helper.make_node("Silu", ["G"], ["S"], name="silu"),
        # Mul is typed to emit BF16 directly: the post-cast dtype, without an
        # unsupported Cast node and without an identity stand-in.
        helper.make_node("Mul", ["S", "U"], ["A16"], name="mul"),
        helper.make_node("Gemm", ["A16", "w_down"], ["Y"], name="gemm_down"),
    ]
    graph = helper.make_graph(
        nodes, "qwen3.5-4b.mlp",
        inputs=[vi("x", bf16, [m, H])],
        outputs=[vi("Y", f32, [m, H])],
        initializer=[zeros("w_gate", bf16, [H, I]), zeros("w_up", bf16, [H, I]),
                     zeros("w_down", bf16, [I, H])],
        value_info=[vi("G", f32, [m, I]), vi("U", f32, [m, I]), vi("S", f32, [m, I]),
                    vi("A16", bf16, [m, I])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
    onnx.save(model, str(path))
    return {
        "path": str(path),
        "sha256": sha256(path),
        "ops": ["Gemm", "Gemm", "Silu", "Mul", "Gemm"],
        "shapes": {"M": m, "H": H, "I": I},
        "dtypes": {"x/w_*/A16": "BFLOAT16 (contract-exact)", "G/U/S/Y": "FLOAT32 (contract-exact)"},
        "declared_deviations": [
            "explicit FP32->BF16 cast has no STREAM parser (see cast_diagnostic): Mul is typed "
            "to emit BF16 directly; post-cast bitwidth/materialisation match the contract, but "
            "the cast's arithmetic work (M*I conversions) is not charged to any node",
            "initializer values are zeros; only shapes and bitwidths are inputs to the analysis",
            "no arithmetic is executed analytically: BF16 rounding happens nowhere here",
        ],
    }


def cmd_cast_diagnostic(args) -> int:
    """Bounded proof that the explicit cast is genuinely unsupported."""
    output = Path(args.output).resolve()
    require(not output.exists(), f"output {output} exists; runs are never overwritten")
    output.mkdir(parents=True)
    result = {"schema": "schedresearch.infra.stream_static.v1", "run_kind": "cast_diagnostic",
              "evaluation_kind": "analytical_static",
              "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        verify_environment(result)
        import_stream(result)
        import onnx  # noqa: PLC0415
        from onnx import TensorProto, helper  # noqa: PLC0415

        model = helper.make_model(helper.make_graph(
            [helper.make_node("Cast", ["a"], ["b"], to=TensorProto.FLOAT16)], "cast_probe",
            inputs=[helper.make_tensor_value_info("a", TensorProto.FLOAT, [4, 4])],
            outputs=[helper.make_tensor_value_info("b", TensorProto.FLOAT16, [4, 4])]))
        probe = output / "cast_probe.onnx"
        onnx.save(model, str(probe))
        from stream.parser.onnx.model import ONNXModelParser  # noqa: PLC0415

        try:
            ONNXModelParser(str(probe)).run()
            result["cast_supported"] = True
        except NotImplementedError as exc:
            result["cast_supported"] = False
            result["parser_error"] = str(exc)
        result["passed"] = result["cast_supported"] is False
    except Exception as exc:  # noqa: BLE001
        result["error"] = {"type": type(exc).__name__, "message": str(exc),
                           "traceback": traceback.format_exc()}
        result["passed"] = False
    (output / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "cast_supported": result.get("cast_supported"),
                      "result": str(output / "result.json")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


def cmd_qwen_mlp(args) -> int:
    output = Path(args.output).resolve()
    require(not output.exists(), f"output {output} exists; runs are never overwritten")
    output.mkdir(parents=True)
    hardware = QWEN_HARDWARE[args.hardware]
    result = {
        "schema": "schedresearch.infra.stream_static.v1",
        "run": "qwen_mlp",
        "evaluation_kind": "analytical_static",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workload_source": {
            "contract": "research/r13/numerical_contract.json",
            "algebra": "down(SiLU(gate(X))*up(X)) with explicit FP32->BF16 cast before down",
            "M": args.m, "H": H, "I": I,
        },
        "hardware_choice": {
            "name": args.hardware,
            "note": "tpu_like_quad_core measured infeasible for the full module "
                    "(33.84 MB resident set vs 2 MiB/core SRAM, 2026-09-13T18-09-33Z run); "
                    "tpu_v7_ironwood is the upstream big-chip example (64 MiB VMEM/TensorCore)",
        },
        "command": " ".join(sys.argv),
        "passed": False,
    }
    previous_cwd = Path.cwd()
    try:
        verify_environment(result)
        api = import_stream(result)
        require(args.m == M_PAD, f"this round admits M={M_PAD} only (padding rule); got M={args.m}")

        model_info = build_qwen_mlp_onnx(output / "qwen_mlp_m32.onnx", m=args.m)
        result["model"] = model_info
        result["inputs"] = {"hardware": {"path": str(hardware), "sha256": sha256(hardware)},
                            "workload": {"path": model_info["path"], "sha256": model_info["sha256"]}}

        from stream.opt.solver import ConstraintSelection, PipeliningModel  # noqa: PLC0415

        # Upstream documents (inputs/examples/mapping/swiglu_tpu_v7_fused.yaml)
        # that the fully-fused SwiGLU chain is structurally infeasible and that
        # a feasible run needs a layer-by-layer split. We measured the fused
        # default infeasible ourselves (runs 2026-09-13T18-09-33Z on
        # tpu_like_quad_core and 2026-09-13T18-15-06Z on tpu_v7_ironwood), so
        # both legal static choices here use the native per-layer split, and
        # the pipelining model is what varies between them.
        configs = [
            ("per_layer_occupancy", ConstraintSelection(pipelining=PipeliningModel.OCCUPANCY)),
            ("per_layer_span", ConstraintSelection(pipelining=PipeliningModel.SPAN)),
        ]
        runs = {}
        for name, selection in configs:
            run = run_allocation(api, hardware, Path(model_info["path"]), f"qwen-mlp-{name}",
                                 output / f"pipeline_{name}", constraint_selection=selection,
                                 fusion_cut_points="per-layer")
            (output / f"allocation_ir_{name}.json").write_text(run.pop("allocation_ir_json"),
                                                             encoding="utf-8")
            runs[name] = run
        result["runs"] = runs

        a, b = runs["per_layer_occupancy"], runs["per_layer_span"]
        structure_changed = (
            a["selected"]["node_core_allocation"] != b["selected"]["node_core_allocation"]
            or a["selected"]["transfer_paths"] != b["selected"]["transfer_paths"]
        )
        result["two_static_choices"] = {
            "same_named_hardware": args.hardware,
            "shared_static_choice": "fusion_cut_points=per-layer (native layer-by-layer split; "
                                    "the fully-fused default is upstream-documented and "
                                    "self-measured as structurally infeasible)",
            "config_a": "constraint_selection.pipelining=occupancy (upstream default)",
            "config_b": "constraint_selection.pipelining=span",
            "selected_structure_changed": structure_changed,
            "analytical_latency_cycles": {
                "occupancy": a["analytical_total_latency_cycles"],
                "span": b["analytical_total_latency_cycles"],
            },
            "note": "different legal static configurations of the same named hardware; "
                    "no speedup is claimed or required",
        }
        for name, run in runs.items():
            require(run["analytical_total_latency_cycles"] > 0, f"{name}: nonpositive latency")
            require(run["selected"]["solve"] is not None
                    and run["selected"]["solve"]["status"] == "OPTIMAL", f"{name}: not OPTIMAL")
        result["passed"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = {"type": type(exc).__name__, "message": str(exc),
                           "traceback": traceback.format_exc()}
    finally:
        os.chdir(previous_cwd)
        status = git("status", "--porcelain")
        result["environment"]["checkout_clean_after"] = not status
        if status:
            result["passed"] = False
            result["source_mutation_detected"] = status
        (output / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    summary = {"passed": result["passed"], "result": str(output / "result.json")}
    if "two_static_choices" in result:
        summary["latency"] = result["two_static_choices"]["analytical_latency_cycles"]
        summary["structure_changed"] = result["two_static_choices"]["selected_structure_changed"]
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if result["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func, helptext in (
        ("native-smoke", cmd_native_smoke, "upstream 2conv fixture on upstream quad-core hardware"),
        ("qwen-mlp", cmd_qwen_mlp, "sourced Qwen MLP through STREAM's native ONNX input"),
        ("cast-diagnostic", cmd_cast_diagnostic, "prove whether ONNX Cast is supported"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--output", type=Path, required=True)
        if name == "qwen-mlp":
            p.add_argument("--m", type=int, default=M_PAD)
            p.add_argument("--hardware", choices=sorted(QWEN_HARDWARE), default="tpu_v7_ironwood")
        p.set_defaults(func=func)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
