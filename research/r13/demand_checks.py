"""R13 independent source-demand and bus-conservation qualifications.

Reads original ONNX plus saved final mapping identity. Does not read an R12
result JSON as an arithmetic oracle, modify R12, or claim a timed protocol.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
import xml.etree.ElementTree as ET

import onnx


ROOT = Path(__file__).resolve().parents[2]
R12 = ROOT / "research/r12"
R13 = ROOT / "research/r13"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_affine_regression() -> dict:
    model_path = R12 / "deps/stream/stream/inputs/testing/workload/2conv_1_8_32_32_16_32_3.onnx"
    base = R12 / "results/baseline_smoke"
    lut_path = base / "pipeline/upstream-2conv/group_0/core_cost_lut.pickle"
    svg_path = base / "pipeline/upstream-2conv/group_0/tetra/steady_state_workload_final.svg"
    ir_path = base / "allocation_ir.json"
    model = onnx.shape_inference.infer_shapes(onnx.load(model_path))
    shapes = {
        value.name: tuple(d.dim_value for d in value.type.tensor_type.shape.dim)
        for value in [*model.graph.input, *model.graph.output, *model.graph.value_info]
    }
    conv = [n for n in model.graph.node if n.op_type == "Conv"]
    require(len(conv) == 2, "The source no longer contains exactly two Conv operators")
    require(conv[1].input[0] == conv[0].output[0], "Changed source edge")
    shape = shapes[conv[0].output[0]]
    attrs = {a.name: onnx.helper.get_attribute_value(a) for a in conv[1].attribute}
    require(shape == (1, 16, 32, 32), "Unexpected intermediate shape")
    require(shapes[conv[1].output[0]] == (1, 32, 32, 32), "Unexpected complete output shape")
    require(attrs["kernel_shape"] == [3, 3] and attrs["pads"] == [1, 1, 1, 1], "Changed source Conv")
    require(attrs.get("strides", [1, 1]) == [1, 1] and attrs.get("dilations", [1, 1]) == [1, 1], "Changed source affine map")
    require(attrs.get("group", 1) == 1, "Grouped convolution needs a different demand derivation")
    source_value = next(v for v in model.graph.value_info if v.name == conv[0].output[0])
    require(source_value.type.tensor_type.elem_type == onnx.TensorProto.BFLOAT16, "The 16-bit data identity changed")
    # This is a locally generated R12 cache, not a downloaded untrusted pickle.
    cache = pickle.loads(lut_path.read_bytes())
    nodes = {node.name: node for node in cache["lut"]}
    labels = ["".join(e.itertext()) for e in ET.fromstring(svg_path.read_text(encoding="utf-8")).iter() if e.tag.endswith("}text")]
    ir = json.loads(ir_path.read_text(encoding="utf-8"))
    mapping = []
    for name in ("Conv1", "Conv2"):
        ordered_names = [p.split("=")[0] for p in labels[labels.index(name) + 1].split()]
        split, factor = ir["mapping_nodes"][name]["inter_core_tiling"][0][0]
        position = ordered_names.index(split)
        output_map = nodes[name].operand_mapping[-1]
        # Probe basis vectors to establish that this final split changes x,
        # independently of assuming a dimension name such as D1 or z13.
        origin = [0] * nodes[name].num_dims
        basis = origin.copy()
        basis[position] = 1
        delta = tuple(a - b for a, b in zip(output_map.eval(basis, ()), output_map.eval(origin, ()), strict=True))
        require(delta == (0, 0, 0, 1) and factor == 4, "Final split is not four-way output x")
        mapping.append({"operator": name, "final_split": split, "factor": factor, "local_position": position, "output_coordinate_delta": delta})

    batch, channels, height, width = shape
    owners = []
    needs = []
    rows = []
    # Derive accesses directly from ONNX Conv indexing. The R12 evaluator and
    # its saved halo JSON are deliberately not called or used for the answer.
    for core in range(4):
        x_begin, x_end = core * width // 4, (core + 1) * width // 4
        owner = {(b, c, y, x) for b in range(batch) for c in range(channels) for y in range(height) for x in range(x_begin, x_end)}
        demand = set()
        for out_y in range(height):
            for out_x in range(x_begin, x_end):
                for dy in range(attrs["kernel_shape"][0]):
                    for dx in range(attrs["kernel_shape"][1]):
                        in_y, in_x = out_y + dy - attrs["pads"][0], out_x + dx - attrs["pads"][1]
                        if 0 <= in_y < height and 0 <= in_x < width:
                            demand.update((0, c, in_y, in_x) for c in range(channels))
        remote = demand - owner
        owners.append(owner)
        needs.append(remote)
        rows.append({"core": core, "output_x_half_open": [x_begin, x_end], "owned_words": len(owner), "distinct_demand_words": len(demand), "remote_words": len(remote), "remote_x": sorted({coord[-1] for coord in remote})})
    require(all(not (a & b) for index, a in enumerate(owners) for b in owners[index + 1:]), "Ownership overlaps")
    all_owned = set().union(*owners)
    remote_union = set().union(*needs)
    require(len(all_owned) == 16384 and remote_union <= all_owned, "Ownership coverage failed")
    require(sum(map(len, needs)) == len(remote_union) == 3072, "Independent affine demand mismatch")
    bits = len(remote_union) * 16
    require(bits == 49152 and (bits + 127) // 128 == 384, "Halo conservation mismatch")
    return {
        "input_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (model_path, lut_path, svg_path, ir_path)},
        "source": "Original ONNX Conv attributes plus independently probed final output affine split identity",
        "intermediate_shape": shape, "mapping": mapping, "per_core": rows,
        "remote_payload_bits": bits, "shared_128_bit_bus_service_lower_bound_cycles": (bits + 127) // 128,
        "ownership_scope": "Continuous aligned owner and consumer x ranges, same core order; a legal demand witness",
        "not_proved": "384 is a necessary service bound; neither a realizable 384-cycle protocol nor correctness of the prior 512-cycle protocol is asserted",
    }


def full_copy_conservation() -> dict:
    words, bits_per_word, capacity = 16384, 16, 128
    owners = [set(range(c * words // 4, (c + 1) * words // 4)) for c in range(4)]
    required = set(range(words))
    remote = [required - owner for owner in owners]
    must_cross = set().union(*remote)
    shared_cycles = (len(must_cross) * bits_per_word + capacity - 1) // capacity
    per_link_cycles = [(len(owner) * bits_per_word + capacity - 1) // capacity for owner in owners]
    require(shared_cycles == 2048 and per_link_cycles == [512] * 4, "Shared versus independent service identity failed")
    require(shared_cycles > 512, "Illegal shared-bus 512-cycle full-copy schedule was accepted")
    return {
        "contract": "Each of four owners initially has a unique quarter; all four destinations require the full tensor; perfect broadcast on the one bus is allowed",
        "distinct_words_crossing_bus": len(must_cross), "minimum_shared_bus_bits": len(must_cross) * bits_per_word,
        "minimum_shared_bus_cycles_with_ideal_broadcast": shared_cycles,
        "remote_deliveries_without_broadcast": sum(map(len, remote)),
        "cycles_without_broadcast": sum(map(len, remote)) * bits_per_word // capacity,
        "invalid_512_cycle_shared_bus_claim_rejected": True,
        "independent_links_positive_control": {"contract": "Four separate source-quarter to distinct-destination transfers, each on its own 128-bit/cycle link; not full all-gather", "bits_per_link": [len(owner) * bits_per_word for owner in owners], "cycles_per_link": per_link_cycles, "parallel_service_lower_bound": max(per_link_cycles)},
    }


def main() -> None:
    result = {"schema": "r13.demand-checks.v1", "status": "passed", "evidence": "Actual independent finite source-access enumeration and integer resource-conservation checks, no timing simulation", "affine_2conv": source_affine_regression(), "explicit_full_copy": full_copy_conservation(), "producer_sha256": digest(Path(__file__))}
    path = R13 / "artifacts/demand_checks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "halo_bits": result["affine_2conv"]["remote_payload_bits"], "halo_bound": 384, "full_copy_bound": 2048, "independent_link_bound": 512, "output": str(path)}))


if __name__ == "__main__":
    main()
