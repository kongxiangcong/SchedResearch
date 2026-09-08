"""Read saved 2conv affine operands and derive actual aligned spatial halo demand.

No optimizer/kernel rerun; explicitly corrects the earlier capacity-to-demand inference.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pickle
import xml.etree.ElementTree as ET


R12 = Path(__file__).resolve().parent
BASE = R12 / "results/baseline_smoke"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    lut_path = BASE / "pipeline/upstream-2conv/group_0/core_cost_lut.pickle"
    svg_path = BASE / "pipeline/upstream-2conv/group_0/tetra/steady_state_workload_final.svg"
    ir_path = BASE / "allocation_ir.json"
    # Locally generated, pinned-source smoke cache; never loading a remote pickle.
    cache = pickle.loads(lut_path.read_bytes())
    nodes = {node.name: node for node in cache["lut"]}
    text = ["".join(e.itertext()) for e in ET.fromstring(svg_path.read_text(encoding="utf-8")).iter() if e.tag.endswith("}text")]
    ir = json.loads(ir_path.read_text(encoding="utf-8"))
    records = {}
    for name in ("Conv1", "Conv2"):
        n = nodes[name]
        label = text[text.index(name) + 1]
        dimension_pairs = [value.split("=") for value in label.split()]
        unique_dims = [pair[0] for pair in dimension_pairs]
        local_sizes = [int(pair[1]) for pair in dimension_pairs]
        tiling = ir["mapping_nodes"][name]["inter_core_tiling"][0]
        split_dim, factor = tiling[0]
        local_position = unique_dims.index(split_dim)
        assert len(unique_dims) == n.num_dims == 7
        assert local_position == 1 and factor == 4
        assert n.outputs[0].shape[3] == local_sizes[1] == 32
        # Source maps are in local (b,ox,oy,fx,fy,c,k) order. Output is NCHW:
        # the output's X coordinate uses local dimension 1, channel uses 6.
        from xdsl.ir.affine import AffineDimExpr
        assert n.operand_mapping[-1].results[3] == AffineDimExpr(1)
        assert n.operand_mapping[-1].results[1] == AffineDimExpr(6)
        records[name] = {
            "saved_source_type": type(n).__module__ + "." + type(n).__name__,
            "operand_affine_maps": [str(m) for m in n.operand_mapping],
            "tensor_names_and_shapes": [{"name": t.name, "shape": list(t.shape)} for t in n.tensors],
            "final_svg_local_dimension_order": unique_dims,
            "final_svg_local_dimension_sizes": local_sizes,
            "final_inter_core_tiling": tiling,
            "split_local_position": local_position,
            "split_axis_meaning": "output spatial x (ox); not output channel k",
            "output_channel_local_position": 6,
        }

    producer, consumer = nodes["Conv1"], nodes["Conv2"]
    output_map = producer.operand_mapping[-1]
    input_map = consumer.operand_mapping[0]
    full_shape = producer.outputs[0].shape
    owned, demanded = [], []
    rows = []
    for core in range(4):
        xs = range(core * 8, (core + 1) * 8)
        source = {
            tuple(output_map.eval((0, ox, oy, 0, 0, 0, k), ()))
            for ox in xs for oy in range(32) for k in range(16)
        }
        demand = set()
        for ox in xs:
            for oy in range(32):
                for fx in range(3):
                    for fy in range(3):
                        for c in range(16):
                            coord = tuple(input_map.eval((0, ox, oy, fx, fy, c, 0), ()))
                            if all(0 <= v < size for v, size in zip(coord, full_shape, strict=True)):
                                demand.add(coord)
        owned.append(source)
        demanded.append(demand)
        remote = demand - source
        rows.append({
            "core": core, "output_x_half_open": [core * 8, (core + 1) * 8],
            "producer_output_words": len(source), "consumer_distinct_input_words": len(demand),
            "consumer_input_x_columns": sorted({p[3] for p in demand}),
            "remote_input_words": len(remote), "remote_input_bits": len(remote) * 16,
            "remote_x_columns": sorted({p[3] for p in remote}),
        })
    all_owned = set.union(*owned)
    remote_sets = [d - s for d, s in zip(demanded, owned, strict=True)]
    union_remote = set.union(*remote_sets)
    assert len(all_owned) == 16384
    assert sum(map(len, remote_sets)) == len(union_remote) == 3072
    assert sorted({p[3] for p in union_remote}) == [7, 8, 15, 16, 23, 24]
    prior_contract = R12 / "shared_resource_counterfactual_contract.json"
    prior_result = R12 / "results/shared_resource_counterfactual/result.json"
    return {
        "schema": "r12.shared-resource-affine-audit.v1",
        "status": "earlier_full_allgather_demand_inference_refuted",
        "evidence_level": "saved real operand maps + final SVG/IR dimension identity + exact finite affine access enumeration",
        "source_artifact_sha256": {str(p.relative_to(R12)): sha(p) for p in (lut_path, svg_path, ir_path)},
        "final_dimension_evidence": records,
        "ownership_assumption": "contiguous aligned ox ranges assigned in core order 0..3 for both operators; this is an allowed static mapping witness, not native address/transfer acceptance",
        "consumer_input_map_note": "input map does not contain output channel k; k=0 suffices to enumerate the same input set for every output channel",
        "per_core_affine_demand": rows,
        "halo_payload_bits": len(union_remote) * 16,
        "halo_shared_bus_conservation_cycles_at_128_bits_per_cycle": len(union_remote) * 16 // 128,
        "full_tensor_bits": 262144,
        "prior_counterfactual_applicability": {
            "original_contract_sha256_preserved": sha(prior_contract),
            "original_result_sha256_preserved": sha(prior_result),
            "original_recorded_analytical_cycles": json.loads(prior_result.read_text(encoding="utf-8"))["analytical_latency_cycles"],
            "prior_full_allgather_scope_justification_supported": False,
            "current_interpretation": "conditional full-payload contract sensitivity; not a confirmed baseline cost repair",
            "original_contract_and_run_files_modified": False,
        },
        "corrections": [
            "Final z6/z13 are local D1=ox spatial dimensions, not output channels.",
            "Allocated full conv1_out_1 footprint does not prove every input is used by each consumer.",
            "2048 is NOT established as a minimum required by the 2conv computation; aligned selective halo needs only 49152 remote bits (384 bus service cycles).",
            "512 is above this necessary halo bound; this audit does not prove an implementable 512-cycle transfer or complete schedule.",
            "The separate parameterized allgather/four-distinct-target shared-bus counterexamples remain valid under their explicit full-payload transfer contracts.",
            "The actual process-overlay solve of 14344 remains a recorded full-payload analytical intervention, not validation of the false allgather data-demand premise or a confirmed P0 repair.",
        ],
        "optimizer_rerun": False, "hardware_measurement": False,
        "producer_sha256": sha(Path(__file__)),
    }


if __name__ == "__main__":
    result = run()
    output = R12 / "artifacts/shared_resource_affine_audit.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "halo_bits": result["halo_payload_bits"], "halo_cycles": 384, "output": str(output)}))
