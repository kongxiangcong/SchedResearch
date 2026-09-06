"""Source-backed, CPU-only fixture for frozen RyzenAI-SW 1.0 qlinear_2.

No XRT loading or device execution. Little endian payloads, M=1 K=N=2048.
The two data-generation algorithms are deterministic and use small signed
integers so the exact INT32 oracle cannot overflow. Source references are in
source_manifest.json; this is not itself a device correctness test.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import struct
import time

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "ryzenai/example/transformers"
OUT = ROOT / "int8_fixture"
M, K, N = 1, 2048, 2048


def wgt_index(row: int, col: int) -> int:
    """Port of WgtMatrix::wgt_idx for the fixed 2048x2048 contract."""
    minor_rows, major_rows, major_cols = K // 4, K // 2, N // 4
    inter_pitch = minor_rows // 512
    zz = (row % 128) * 8 + col % 8 + (col % 64 // 8) * 1024
    inter = (col % major_cols // 64) * inter_pitch + row % minor_rows // 512
    off1 = row // 128 % 4
    off2 = row // minor_rows % 2 + inter * 2
    off3 = col // major_cols * 2 + row // major_rows
    return zz + off1 * 8192 + off2 * 32768 + off3 * major_rows * major_cols


def super_sequence() -> bytes:
    # MLKernelParams default constructor, then update_params(32,128,64,8,8,16),
    # then ctrl.parts.out_32=1. Native C++ little-endian struct size is 40 B.
    params = struct.pack(
        "<BBBbBBBBHHbbbb8HiI",
        0, 0, 0, 0, 16, 4, 4, 0, 16, 16, 12, 12, 0, 0,
        1024, 8, 0, 256, 8, 256, 8, 0, 0, 773 | (1 << 10),
    )
    assert len(params) == 40
    # GemmSeq header12 + 3*GemmInstr60 + padding8 =200B. Unused/padding
    # bytes are explicitly zeroed (the C++ initializer leaves them unchanged).
    result = struct.pack("<iiHH", 48, 0, 8, 48)
    for size, repeat, subsize, opcode in (
        (15, 1, 48, 0x02010D01),
        (15, 2, 48, 0x02010C01),
        (17, 1, 56, 0x02010E01),
    ):
        result += struct.pack("<hhIIII", size, repeat, 0x003C000F, 128, subsize, opcode)
        result += params
    result += bytes(8)
    assert len(result) == 200
    return result


def main() -> None:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    # random.Random is used only to prepare a frozen input, whose exact bytes
    # are authoritative after generation; neither seed alone nor PRNG-version
    # compatibility is relied upon at device execution time.
    rng = random.Random(0x5237434F)
    a = [rng.randrange(-3, 4) for _ in range(K)]
    w = [rng.randrange(-3, 4) for _ in range(K * N)]
    packed = bytearray(K * N)
    seen = bytearray(K * N)
    expected = [0] * N
    for row in range(K):
        a_value = a[row]
        for col in range(N):
            source_index = row * N + col
            index = wgt_index(row, col)
            if index < 0 or index >= len(packed) or seen[index]:
                raise ValueError("weight map is not a permutation")
            seen[index] = 1
            value = w[source_index]
            packed[index] = value & 255
            expected[col] += a_value * value
    assert all(seen)
    assert len(set(expected)) > 50, "oracle should discriminate outputs"
    text_path = SRC / "dll/phx/qlinear_2/mc_code_1_2k_2k.txt"
    words = [int(line, 16) for line in text_path.read_text().splitlines()
             if line and not line.startswith("#")]
    files = {
        "a_rowmajor_int8.bin": bytes(value & 255 for value in a),
        "weights_rowmajor_int8.bin": bytes(value & 255 for value in w),
        "weights_packed_int8.bin": bytes(packed),
        "super_sequence.bin": super_sequence(),
        "a_with_super_sequence.bin": bytes(value & 255 for value in a) + super_sequence(),
        "instructions_uint32.bin": struct.pack(f"<{len(words)}I", *words),
        "expected_rowmajor_int32.bin": struct.pack(f"<{N}i", *expected),
    }
    manifest = {
        "evidence_level": "source-derived CPU-only fixture, no device execution",
        "source_revision": "a3d163c81e4d0b21667c05f614c1d79be14c3fa1",
        "shape": [M, K, N], "dtype": "int8*int8->int32", "byteorder": "little",
        "device_kernel": "DPU", "opcode_uint64": 1,
        "args": ["uint64(1)", "A_BO(2248)", "W_BO(4194304)", "C_BO(8192)",
                 "dummy_BO(16)", f"instr_BO({len(words)*4})", f"uint32({len(words)})", "dummy_BO(16)"],
        "xclbin": str(SRC / "xclbin/phx/gemm_4x4.xclbin"),
        "instruction_words": len(words), "weight_map_verified_bijection": True,
        "oracle": "exact signed integer sum over the unformatted row-major weights",
        "output_min": min(expected), "output_max": max(expected),
        "distinct_outputs": len(set(expected)),
        "files": {},
    }
    for name, data in files.items():
        (OUT / name).write_bytes(data)
        manifest["files"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    manifest["cpu_fixture_generation_seconds"] = time.perf_counter() - started
    (OUT / "fixture_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
