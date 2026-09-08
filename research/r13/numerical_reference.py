"""Execute R13's full MLP numerical contract and an independent CPU checker.

FP64 BLAS evaluates the unquantized source algebra on the same BF16 inputs.
Neither FP32 BLAS nor a vendor kernel is used as a fixed-tree arithmetic oracle.
Generated tensors stay in memory; JSON contains shape/hash/error evidence only.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

# Fixed before NumPy is imported; this controls source-algebra BLAS only.
os.environ["OPENBLAS_NUM_THREADS"] = "4"
os.environ["OMP_NUM_THREADS"] = "4"
import numpy as np


HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "numerical_contract.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def array_sha(array: np.ndarray) -> str:
    return sha(np.ascontiguousarray(array).tobytes())


def bf16_bits_round(values: np.ndarray) -> np.ndarray:
    """Finite FP32 to BF16 RNE by integer discarded-bit accounting."""
    data = np.asarray(values, dtype=np.float32)
    bits = data.view(np.uint32)
    rounded = bits + np.uint32(0x7FFF) + ((bits >> np.uint32(16)) & np.uint32(1))
    return (rounded & np.uint32(0xFFFF0000)).view(np.float32)


def bf16_arithmetic_round(values: np.ndarray) -> np.ndarray:
    """Independent normal/subnormal finite conversion using power-of-two grids."""
    values64 = np.asarray(values, dtype=np.float64)
    _, exponent = np.frexp(np.abs(values64))
    spacing = np.exp2(np.maximum(exponent - 8, -133).astype(np.float64))
    with np.errstate(over="ignore"):
        rounded = (np.rint(values64 / spacing) * spacing).astype(np.float32)
    return np.copysign(rounded, values64).astype(np.float32)


def gemm_materialized_tree(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Materialize 32 products, reduce adjacent slices, accumulate block sums."""
    m, k = left.shape
    require(right.shape[0] == k and k % 32 == 0, "Invalid GEMM shape")
    output = np.zeros((m, right.shape[1]), dtype=np.float32)
    for column in range(0, right.shape[1], 256):
        end = min(column + 256, right.shape[1])
        accumulator = np.zeros((m, end - column), dtype=np.float32)
        for block in range(0, k, 32):
            products = left[:, block:block + 32, None] * right[None, block:block + 32, column:end]
            while products.shape[1] > 1:
                products = np.add(products[:, 0::2, :], products[:, 1::2, :], dtype=np.float32)
            np.add(accumulator, products[:, 0, :], out=accumulator)
        output[:, column:end] = accumulator
    return output


def gemm_carry_checker(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Independent streaming K walk with a binary carry stack per 32 products."""
    rows, length = left.shape
    require(right.shape[0] == length and length % 32 == 0, "Checker shape mismatch")
    answer = np.empty((rows, right.shape[1]), dtype=np.float32)
    # Different output blocking has no effect on the prescribed K tree.
    for start in range(0, right.shape[1], 384):
        stop = min(start + 384, right.shape[1])
        total = np.zeros((rows, stop - start), dtype=np.float32)
        levels: list[np.ndarray | None] = [None] * 6
        for index in range(length):
            value = np.multiply(left[:, index, None], right[None, index, start:stop], dtype=np.float32)
            level = 0
            position = index % 32
            while position & (1 << level):
                value = np.add(levels[level], value, dtype=np.float32)
                levels[level] = None
                level += 1
            levels[level] = value
            if index % 32 == 31:
                total = np.add(total, levels[5], dtype=np.float32)
                levels[5] = None
        answer[:, start:stop] = total
    return answer


def silu_vector(values: np.ndarray) -> np.ndarray:
    positive = values >= 0
    exponent = np.where(positive, -values.astype(np.float64), values.astype(np.float64))
    e = np.exp(exponent).astype(np.float32)
    denominator = np.add(np.float32(1), e, dtype=np.float32)
    numerator = np.where(positive, values, np.multiply(values, e, dtype=np.float32))
    return np.divide(numerator, denominator, dtype=np.float32)


def silu_scalar_checker(values: np.ndarray) -> np.ndarray:
    def scalar(value: np.float32) -> np.float32:
        x = float(value)
        if x >= 0:
            e = np.float32(math.exp(-x))
            return np.float32(value / np.float32(np.float32(1) + e))
        e = np.float32(math.exp(x))
        return np.float32(np.float32(value * e) / np.float32(np.float32(1) + e))

    return np.fromiter((scalar(x) for x in values.flat), dtype=np.float32, count=values.size).reshape(values.shape)


def bit_equal(a: np.ndarray, b: np.ndarray, label: str) -> None:
    require(a.shape == b.shape and np.array_equal(a.view(np.uint32), b.view(np.uint32)), f"Independent arithmetic mismatch: {label}")


def make_tensor(shape: tuple[int, int], seed: int, scale: float) -> np.ndarray:
    generator = np.random.Generator(np.random.PCG64(seed))
    raw = ((2 * generator.random(shape) - 1) * scale).astype(np.float32)
    rounded = bf16_bits_round(raw)
    # Check every generated initial BF16 conversion by a separate algorithm.
    bit_equal(rounded, bf16_arithmetic_round(raw), f"initial BF16 seed {seed}")
    return rounded


def unit_checks() -> dict:
    tie_bits = np.array([0x3F808000, 0x3F818000, 0xBF808000, 0xBF818000, 0x00008000, 0x00018000, 0x80008000, 0x80018000, 0x00000000, 0x80000000], dtype=np.uint32)
    expected = np.array([0x3F800000, 0x3F820000, 0xBF800000, 0xBF820000, 0x00000000, 0x00020000, 0x80000000, 0x80020000, 0x00000000, 0x80000000], dtype=np.uint32)
    require(np.array_equal(bf16_bits_round(tie_bits.view(np.float32)).view(np.uint32), expected), "BF16 tie-to-even failed")
    bit_equal(bf16_bits_round(tie_bits.view(np.float32)), bf16_arithmetic_round(tie_bits.view(np.float32)), "BF16 ties")
    rng = np.random.Generator(np.random.PCG64(20260912))
    patterns = rng.integers(0, 2**32, 101000, dtype=np.uint32)
    patterns = patterns[((patterns >> 23) & 255) != 255][:100000]
    require(len(patterns) == 100000, "Insufficient finite rounding probes")
    bit_equal(bf16_bits_round(patterns.view(np.float32)), bf16_arithmetic_round(patterns.view(np.float32)), "finite bit-pattern BF16 conversion")
    # The prescribed pair tree produces one (the negative-side unit is exactly
    # representable); first cancelling the large terms would produce two.
    # All multiplicands are BF16 exact, so this isolates FP32 reassociation.
    a = np.zeros((1, 32), dtype=np.float32)
    a[0, :4] = [2**24, 1, -(2**24), 1]
    b = np.ones((32, 1), dtype=np.float32)
    main = gemm_materialized_tree(a, b)
    checker = gemm_carry_checker(a, b)
    bit_equal(main, checker, "cancellation")
    forbidden = np.float32(np.float32(a[0, 0] + a[0, 2]) + np.float32(a[0, 1] + a[0, 3]))
    require(main[0, 0] != forbidden, "Reassociation mutant was not detected")
    extremes = np.array([-100, -20, -1, -0.0, 0.0, 1, 20, 100], dtype=np.float32)
    bit_equal(silu_vector(extremes), silu_scalar_checker(extremes), "SiLU extremes")
    cast_values = np.linspace(-2.1, 2.1, 32, dtype=np.float32).reshape(1, 32)
    mut_weights = make_tensor((32, 16), 20260913, 1)
    cast_y = gemm_materialized_tree(bf16_bits_round(cast_values), mut_weights)
    illegal_y = gemm_materialized_tree(cast_values, mut_weights)
    require(not np.array_equal(cast_y, illegal_y), "Omitted down-input cast mutant was not detected")
    return {"passed": True, "bf16_tie_cases": len(tie_bits), "finite_fp32_rounding_cases": len(patterns), "silu_extreme_cases": len(extremes), "cancellation_tree_result": float(main[0, 0]), "forbidden_reassociation_result": float(forbidden), "omitted_cast_mutation_detected": True, "omitted_cast_max_absolute_difference": float(np.max(np.abs(cast_y - illegal_y)))}


def compare_fp64(model: np.ndarray, source: np.ndarray, contract: dict) -> dict:
    difference = model.astype(np.float64) - source
    denominator = max(float(np.linalg.norm(source)), contract["acceptance"]["source_algebra_atol_floor"])
    maximum = max(float(np.max(np.abs(source))), contract["acceptance"]["source_algebra_atol_floor"])
    relative_l2 = float(np.linalg.norm(difference) / denominator)
    scaled_maximum = float(np.max(np.abs(difference)) / maximum)
    require(relative_l2 <= contract["acceptance"]["source_algebra_relative_l2_max"], "Source-algebra relative L2 threshold failed")
    require(scaled_maximum <= contract["acceptance"]["source_algebra_max_abs_over_max_abs_reference_max"], "Source-algebra scaled max threshold failed")
    return {"relative_l2": relative_l2, "max_abs_error": float(np.max(np.abs(difference))), "max_abs_over_max_abs_source": scaled_maximum, "max_pointwise_relative_error_at_1e_minus12_floor": float(np.max(np.abs(difference) / np.maximum(np.abs(source), 1e-12))), "reference_max_abs": maximum, "reference_sha256": array_sha(source), "passed": True}


def execute_case(m: int, x_all: np.ndarray, weights: dict[str, np.ndarray], contract: dict) -> dict:
    start = time.perf_counter()
    padded_m = (m + 31) // 32 * 32
    x = np.zeros((padded_m, contract["source"]["H"]), dtype=np.float32)
    x[:m] = x_all[:m]
    arrays = {}
    checks = {}
    for projection in ("gate", "up"):
        result = gemm_materialized_tree(x, weights[projection])
        independent = gemm_carry_checker(x, weights[projection])
        bit_equal(result, independent, f"M={m} {projection}")
        arrays[projection] = result
        checks[projection] = {"shape": list(result.shape), "sha256": array_sha(result), "bitwise_independent_match": True}
        print(json.dumps({"progress": f"M={m} {projection} primary and checker complete", "seconds": round(time.perf_counter() - start, 3)}), flush=True)
    s = silu_vector(arrays["gate"])
    s_check = silu_scalar_checker(arrays["gate"])
    bit_equal(s, s_check, f"M={m} SiLU")
    a = np.multiply(s, arrays["up"], dtype=np.float32)
    # Multiplication has no reduction; checker uses FP64 exact product followed
    # by FP32 rounding, independent of the primary FP32 multiply ufunc path.
    a_check = (s_check.astype(np.float64) * arrays["up"].astype(np.float64)).astype(np.float32)
    bit_equal(a, a_check, f"M={m} elementwise multiply")
    a_bf16 = bf16_bits_round(a)
    a_bf16_check = bf16_arithmetic_round(a_check)
    bit_equal(a_bf16, a_bf16_check, f"M={m} down-input cast")
    y = gemm_materialized_tree(a_bf16, weights["down"])
    y_check = gemm_carry_checker(a_bf16_check, weights["down"])
    bit_equal(y, y_check, f"M={m} down")
    for name, values in (("silu", s), ("multiply_fp32", a), ("down_input_bf16", a_bf16), ("down", y)):
        require(bool(np.all(np.isfinite(values))), f"Non-finite {name}")
        if padded_m > m:
            require(bool(np.all(values[m:] == 0)), f"Nonzero padding in {name}")
        checks[name] = {"shape": list(values.shape), "sha256": array_sha(values), "bitwise_independent_match": True}
    # Independent full source algebra: same BF16 inputs, FP64 GEMMs/SiLU/mul,
    # no artificial BF16 cast inserted between the mathematical source nodes.
    x64 = x[:m].astype(np.float64)
    gate64 = x64 @ weights["gate"].astype(np.float64)
    up64 = x64 @ weights["up"].astype(np.float64)
    source_y = (gate64 / (1 + np.exp(-gate64)) * up64) @ weights["down"].astype(np.float64)
    metrics = compare_fp64(y[:m], source_y, contract)
    h, intermediate = contract["source"]["H"], contract["source"]["I"]
    elapsed = time.perf_counter() - start
    print(json.dumps({"progress": f"M={m} full numerical qualification passed", "seconds": round(elapsed, 3), "relative_l2": metrics["relative_l2"]}), flush=True)
    return {"M": m, "padded_M": padded_m, "all_output_elements_checked": m * h, "all_padded_output_elements_checked": padded_m * h, "logical_MACs": 3 * m * h * intermediate, "padded_MACs": 3 * padded_m * h * intermediate, "input_bf16_bytes": 2 * m * h, "output_fp32_bytes": 4 * m * h, "cast_elements": m * intermediate, "cast_logical_read_bytes": 4 * m * intermediate, "cast_logical_write_bytes": 2 * m * intermediate, "checks": checks, "source_algebra_error": metrics, "output_logical_sha256": array_sha(y[:m]), "cpu_validation_wall_seconds_not_model_cycles": elapsed, "passed": True}


def main() -> None:
    start = time.perf_counter()
    raw_contract = CONTRACT_PATH.read_bytes()
    contract = json.loads(raw_contract)
    require(contract["frozen_before_execution"] is True, "Numerical contract must be frozen first")
    require(np.__version__ == contract["generation"]["numpy_version"], "NumPy version drift requires an explicit contract revision")
    units = unit_checks()
    h, intermediate = contract["source"]["H"], contract["source"]["I"]
    seeds = contract["generation"]["seeds"]
    x = make_tensor((max(contract["source"]["M"]), h), seeds["X"], 1)
    weights = {}
    for name, shape in (("gate", (h, intermediate)), ("up", (h, intermediate)), ("down", (intermediate, h))):
        weights[name] = make_tensor(shape, seeds[name], math.sqrt(3 / shape[0]))
    tensors = {name: {"shape": list(array.shape), "storage_dtype": "BF16 represented exactly in FP32 CPU arrays", "sha256_of_fp32_representation": array_sha(array)} for name, array in {"X": x, **weights}.items()}
    print(json.dumps({"progress": "All generated initial tensors independently BF16 checked", "seconds": round(time.perf_counter() - start, 3)}), flush=True)
    cases = [execute_case(m, x, weights, contract) for m in contract["source"]["M"]]
    require(CONTRACT_PATH.read_bytes() == raw_contract, "Contract changed during execution")
    result = {"schema": "r13.numerical-qualification.v1", "status": "passed", "evidence": "Actual CPU execution of complete MLPs and independent fixed-tree checks; no hardware, model timing, downloaded trained weights, or end-task accuracy claim", "contract_sha256": sha(raw_contract), "producer_sha256": sha(Path(__file__).read_bytes()), "environment": {"python": sys.version, "numpy": np.__version__, "platform": platform.platform(), "blas_threads": 4}, "units": units, "initial_tensors": tensors, "cases": cases, "total_cpu_validation_wall_seconds_not_model_cycles": time.perf_counter() - start}
    output = HERE / "artifacts/numerical_qualification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "M": [c["M"] for c in cases], "relative_l2": [c["source_algebra_error"]["relative_l2"] for c in cases], "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
