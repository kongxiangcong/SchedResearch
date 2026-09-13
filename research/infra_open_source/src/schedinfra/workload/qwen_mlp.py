"""Sourced Qwen3.5-4B MLP module specification and workload accounting.

Source of truth
---------------
`research/r13/numerical_contract.json` (frozen 2026-09-08), which records:

* model `Qwen/Qwen3.5-4B`, revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`
* algebra ``down(BF16(SiLU(gate(X)) * up(X)))``
* H = 2560, I = 9216, M in {1, 32, 128}, no bias

This module deliberately contains **no** timing numbers. It describes algebra,
shapes, dtypes, MAC/byte counts and the explicit padding rule. Anything about
cycles belongs to a backend, not here.

Deliberate non-negotiable semantics (from the frozen contract)
--------------------------------------------------------------
* SiLU is kept as SiLU. It is never substituted with ReLU or GeLU.
* The elementwise multiply and the FP32->BF16 cast before `down` are explicit
  ops. They may be *fused* by a plan (avoiding materialisation) but they may
  never be dropped from the arithmetic inventory.
* M is padded up to a multiple of 32; padded rows must stay zero and their MACs
  are charged to any physical plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..repo import NUMERICAL_CONTRACT, sha256_file, sha256_json

# Tile granularity fixed by the contract's padding rule.
TILE_M = 32
TILE_K = 32
TILE_N = 32

H = 2560
I = 9216

DTYPE_BYTES = {"BF16": 2, "FP32": 4}


@dataclass(frozen=True)
class TensorSpec:
    name: str
    shape: tuple[int, ...]
    dtype: str
    producer: str | None = None  # None => module input or weight (external)
    kind: str = "activation"  # activation | weight | output

    @property
    def elements(self) -> int:
        total = 1
        for dim in self.shape:
            total *= dim
        return total

    @property
    def bytes(self) -> int:
        return self.elements * DTYPE_BYTES[self.dtype]


@dataclass(frozen=True)
class OpSpec:
    id: str
    kind: str  # gemm | silu | mul | cast_bf16
    inputs: tuple[str, ...]
    output: str
    notes: str = ""

    def logical_macs(self, padded_m: int) -> int:
        if self.kind != "gemm":
            return 0
        if self.id == "gemm_down":
            return padded_m * I * H
        return padded_m * H * I

    def logical_elements(self, padded_m: int) -> int:
        if self.kind == "gemm":
            return padded_m * (I if self.id != "gemm_down" else H)
        return padded_m * I

    def is_elementwise(self) -> bool:
        return self.kind in {"silu", "mul", "cast_bf16"}


OPS: tuple[OpSpec, ...] = (
    OpSpec("gemm_gate", "gemm", ("x", "w_gate"), "G",
           "X @ W_gate, K = H = 2560 must stay complete; no K shrinking."),
    OpSpec("gemm_up", "gemm", ("x", "w_up"), "U",
           "X @ W_up, same complete K dimension."),
    OpSpec("silu", "silu", ("G",), "S",
           "SiLU on FP32 G. Substituting ReLU/GeLU is forbidden."),
    OpSpec("mul", "mul", ("S", "U"), "A32",
           "Elementwise product; A32 = round32(S * U)."),
    OpSpec("cast_bf16", "cast_bf16", ("A32",), "A16",
           "Explicit FP32->BF16 RNE cast before down. May be fused, not dropped."),
    OpSpec("gemm_down", "gemm", ("A16", "w_down"), "Y",
           "A16 @ W_down, K = I = 9216 complete; output FP32 [M, H]."),
)

# Dependency edges of the module graph (op id -> ops it must wait for).
OP_DEPS: dict[str, tuple[str, ...]] = {
    "gemm_gate": (),
    "gemm_up": (),
    "silu": ("gemm_gate",),
    "mul": ("silu", "gemm_up"),
    "cast_bf16": ("mul",),
    "gemm_down": ("cast_bf16",),
}


def padded_m(m: int) -> int:
    return ((m + TILE_M - 1) // TILE_M) * TILE_M


@dataclass(frozen=True)
class MLPModule:
    """One concrete instantiation of the MLP for a given token count M."""

    m: int
    h: int = H
    i: int = I

    def __post_init__(self) -> None:
        if self.m < 1:
            raise ValueError("M must be >= 1")
        if self.h != H or self.i != I:
            raise ValueError(
                "This sourced module fixes H=2560, I=9216; a different shape "
                "needs a new frozen contract, not a silent parameter change."
            )

    @property
    def m_pad(self) -> int:
        return padded_m(self.m)

    @property
    def padded_rows(self) -> int:
        return self.m_pad - self.m

    # ---- tensors -----------------------------------------------------
    def tensors(self) -> dict[str, TensorSpec]:
        mp = self.m_pad
        return {
            "x": TensorSpec("x", (mp, self.h), "BF16", None, "activation"),
            "w_gate": TensorSpec("w_gate", (self.h, self.i), "BF16", None, "weight"),
            "w_up": TensorSpec("w_up", (self.h, self.i), "BF16", None, "weight"),
            "w_down": TensorSpec("w_down", (self.i, self.h), "BF16", None, "weight"),
            "G": TensorSpec("G", (mp, self.i), "FP32", "gemm_gate"),
            "U": TensorSpec("U", (mp, self.i), "FP32", "gemm_up"),
            "S": TensorSpec("S", (mp, self.i), "FP32", "silu"),
            "A32": TensorSpec("A32", (mp, self.i), "FP32", "mul"),
            "A16": TensorSpec("A16", (mp, self.i), "BF16", "cast_bf16"),
            "Y": TensorSpec("Y", (mp, self.h), "FP32", "gemm_down", "output"),
        }

    # ---- accounting ---------------------------------------------------
    def logical_macs(self) -> int:
        return 3 * self.m * self.h * self.i

    def padded_macs(self) -> int:
        return 3 * self.m_pad * self.h * self.i

    def weight_bytes(self) -> int:
        return 3 * self.h * self.i * DTYPE_BYTES["BF16"]

    def input_bytes(self) -> int:
        return self.m * self.h * DTYPE_BYTES["BF16"]

    def output_bytes(self) -> int:
        return self.m * self.h * DTYPE_BYTES["FP32"]

    def activation_bytes(self) -> dict[str, int]:
        tensors = self.tensors()
        return {name: tensors[name].bytes for name in ("G", "U", "S", "A32", "A16", "Y")}

    def cast_work(self) -> dict[str, int]:
        """Explicit cast is charged even if a plan fuses it away physically."""
        elements = self.m_pad * self.i
        return {
            "elements": elements,
            "logical_read_bytes": elements * DTYPE_BYTES["FP32"],
            "logical_write_bytes": elements * DTYPE_BYTES["BF16"],
        }

    def inventory(self) -> dict[str, Any]:
        return {
            "M": self.m,
            "padded_M": self.m_pad,
            "padded_rows": self.padded_rows,
            "H": self.h,
            "I": self.i,
            "logical_MACs": self.logical_macs(),
            "padded_MACs": self.padded_macs(),
            "weight_bytes_bf16": self.weight_bytes(),
            "input_bytes_bf16": self.input_bytes(),
            "output_bytes_fp32": self.output_bytes(),
            "activation_bytes": self.activation_bytes(),
            "explicit_cast": self.cast_work(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": "qwen3.5-4b.mlp",
            "M": self.m,
            "padded_M": self.m_pad,
            "H": self.h,
            "I": self.i,
            "ops": [
                {
                    "id": op.id,
                    "kind": op.kind,
                    "inputs": list(op.inputs),
                    "output": op.output,
                    "deps": list(OP_DEPS[op.id]),
                    "logical_macs": op.logical_macs(self.m_pad),
                    "logical_elements": op.logical_elements(self.m_pad),
                    "notes": op.notes,
                }
                for op in OPS
            ],
            "tensors": {
                name: {"shape": list(spec.shape), "dtype": spec.dtype, "bytes": spec.bytes,
                       "producer": spec.producer, "kind": spec.kind}
                for name, spec in self.tensors().items()
            },
            "inventory": self.inventory(),
        }


def load_contract() -> dict[str, Any]:
    return json.loads(NUMERICAL_CONTRACT.read_text(encoding="utf-8"))


def contract_identity() -> dict[str, Any]:
    """Provenance for the frozen numerical contract this module mirrors."""
    contract = load_contract()
    return {
        "path": "research/r13/numerical_contract.json",
        "sha256": sha256_file(NUMERICAL_CONTRACT),
        "model": contract["source"]["model"],
        "model_revision": contract["source"]["model_revision"],
        "transformers_revision": contract["source"]["transformers_revision"],
        "algebra": contract["source"]["algebra"],
        "H": contract["source"]["H"],
        "I": contract["source"]["I"],
        "M_allowed": contract["source"]["M"],
        "k_block": contract["gemm"]["k_block"],
        "reassociation": contract["gemm"]["reassociation"],
        "padding": contract["padding"],
    }


def workload_identity(m: int) -> dict[str, Any]:
    module = MLPModule(m)
    return {
        "module": "qwen3.5-4b.mlp",
        "M": m,
        "padded_M": module.m_pad,
        "H": H,
        "I": I,
        "contract": contract_identity(),
        "inventory_hash": sha256_json(module.inventory()),
        "graph_hash": sha256_json(module.to_dict()),
    }
