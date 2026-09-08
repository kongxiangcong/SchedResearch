"""Descriptive analysis of the frozen micro experiment; no candidate selection."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(rows, a, b, scenarios):
    result = []
    for scenario in scenarios:
        ra, rb = rows[scenario,a], rows[scenario,b]
        ok = ra["status"] == rb["status"] == "valid"
        effects = {}
        for metric in ("output_visible","final_ack","quiescent"):
            ta, tb = ra["model_ticks"][metric], rb["model_ticks"][metric]
            effects[metric] = None if not ok else {
                "A_ticks":ta, "B_ticks":tb, "B_improvement_over_A_percent":100*(ta-tb)/ta}
        result.append({"scenario":scenario,"params":ra["params"],"both_valid":ok,"effects":effects})
    values = [r["effects"]["output_visible"]["B_improvement_over_A_percent"] for r in result if r["both_valid"]]
    return {"A":a,"B":b,"positive_means":"B lower output-visible than A; denominator A",
        "points":result,"range_percent":[min(values),max(values)],
        "positive_zero_negative":[sum(v>0 for v in values),sum(v==0 for v in values),sum(v<0 for v in values)]}


def main():
    files = ["preregistration_serial.json","artifacts/micro_nominal.json","artifacts/micro_witnesses.json"]
    reg, nominal, witness = map(load,files)
    registered_ids = {p["id"] for p in reg["candidates"]}
    assert len(nominal["rows"]) == len(registered_ids) == 576
    assert {r["plan_id"] for r in nominal["rows"]} == registered_ids
    assert nominal["source_sha256"] == witness["source_sha256"] == reg["source_sha256"]
    assert nominal["registration_sha256"] == witness["registration_sha256"] == sha(ROOT/files[0])
    wr = {(r["scenario"],r["plan_id"]):r for r in witness["rows"]}
    scenarios = [f"parameter_{i:02}" for i in range(len(reg["parameter_points"]))]
    structural = ["mono_nominal","descending_nominal"]
    expected_keys = {(s,p) for s in scenarios+structural for p in reg["unique_witness_plans"]}
    assert len(wr) == len(witness["rows"]) == len(expected_keys) == 168
    assert set(wr) == expected_keys
    comparisons = {
        "equal_aggregate_protocol_routes": tuple(reg["witnesses"]["links"]["plans"]),
        "input_channel_separation": tuple(reg["witnesses"]["channels"]["plans"][:2]),
        "source_reuse_vs_ack_wait": tuple(reversed(reg["witnesses"]["reuse"]["plans"]))}
    effects = {name:compare(wr,a,b,scenarios) for name,(a,b) in comparisons.items()}
    structures = {name:compare(wr,a,b,structural) for name,(a,b) in comparisons.items()}
    nominal_rows = {p:wr["parameter_00",p] for p in reg["unique_witness_plans"]}
    source_events = nominal_rows["p0000"]["source_receive_output_events"]
    reuse_examples = []
    for chain in (0,1):
        old = next(r for r in source_events if r["chain"]==chain and r["epoch"]==0)
        new = next(r for r in source_events if r["chain"]==chain and r["epoch"]==1)
        reuse_examples.append({"chain":chain,"old_source_last_read":old["peer_source_last_read"],
            "old_source_observed":old["peer_source_observed"],"new_load_issue_start":new["load_issue_start"],
            "old_peer_ack":old["peer_ack"],
            "legal_before_ack":old["peer_source_observed"] <= new["load_issue_start"] < old["peer_ack"]})
    channel_a,channel_b = nominal_rows["p0000"],nominal_rows["p0048"]
    assert channel_a["traffic_ledger"]["link_flits"] == channel_b["traffic_ledger"]["link_flits"]
    link_a,link_b = [nominal_rows[p] for p in comparisons["equal_aggregate_protocol_routes"]]
    assert link_a["traffic_ledger"]["by_role"] == link_b["traffic_ledger"]["by_role"]
    assert link_a["traffic_ledger"]["packet_hops"] != link_b["traffic_ledger"]["packet_hops"]
    receipt = {"schema":"r13.micro-analysis.v1","input_sha256":{p:sha(ROOT/p) for p in files},
        "producer_sha256":sha(Path(__file__).resolve()),
        "coverage":{"nominal_unique":576,"witness_unique":168,
            "nominal_valid":sum(r["status"]=="valid" for r in nominal["rows"]),
            "witness_valid":sum(r["status"]=="valid" for r in witness["rows"]),
            "same_frozen_sources":True},
        "exact_and_diagnostic_regret":nominal["summary"],
        "frozen_plan_parameter_effects":effects,"structural_effects":structures,
        "reuse_event_examples_ticks":reuse_examples,
        "channel_service_nominal_ticks":{"alias":channel_a["per_channel_service_ticks"],"separate":channel_b["per_channel_service_ticks"]},
        "nominal_selected_plans": {p:{"model_cycles":r["model_cycles"],"estimator_scores":r["estimator_scores"],
            "full_protocol_flit_hops":r["traffic_ledger"]["full_protocol_flit_hops"],
            "cross_chain_router_shared_flits":r["traffic_ledger"]["cross_chain_router_shared_flits"]} for p,r in nominal_rows.items()},
        "inference_limits":["No full MLP simulation or M2 decision", "No Hcompiler test or complete strong P0 portfolio",
            "Route pair does not isolate pure contention", "Sensitivity points are a discrete model domain, not random samples"]}
    out = ROOT/"artifacts/micro_analysis.json"
    with out.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(receipt,f,indent=2,ensure_ascii=False); f.write("\n")
    with (ROOT/"artifacts/micro_nominal.csv").open("x",encoding="utf-8",newline="") as f:
        cols = ["plan_id","status","output_visible_cycles","final_ack_cycles","quiescent_cycles",
                "payload_router_byte_hops","full_protocol_flit_hops","dependency_only_DAG_ticks"]
        writer = csv.writer(f); writer.writerow(cols)
        for r in nominal["rows"]:
            writer.writerow([r["plan_id"],r["status"],*r["model_cycles"].values(),*r["estimator_scores"].values()])
    make_figure(receipt)
    print(json.dumps({"coverage":receipt["coverage"],"exact":nominal["summary"]["exact"],
        "effects":{k:{"range":v["range_percent"],"signs":v["positive_zero_negative"]} for k,v in effects.items()}}))


def make_figure(receipt):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(1,3,figsize=(12,3.4),sharey=True,constrained_layout=True)
    titles = ["Equal aggregate protocol traffic\nroute pair (confounded)",
              "Same endpoints and routes\nseparate input channel", "Legal source reuse\nversus ACK wait (ablation)"]
    for ax,(name,data),title in zip(axes,receipt["frozen_plan_parameter_effects"].items(),titles):
        y = [r["effects"]["output_visible"]["B_improvement_over_A_percent"] for r in data["points"]]
        ax.axhline(0,color="#555555",linewidth=.8)
        ax.scatter(range(len(y)),y,s=21,color="#1565a8",zorder=3)
        ax.scatter([0],[y[0]],s=62,facecolors="none",edgecolors="#c64918",linewidths=1.5,zorder=4)
        ax.set_title(title,fontsize=10)
        ax.set_xlabel("Registered scenario index (nominal = 0)",fontsize=9)
        ax.set_xticks([0,5,10,15,20,25]); ax.grid(axis="y",alpha=.18)
        ax.spines[["top","right"]].set_visible(False)
    axes[0].set_ylabel("Output-visible reduction, B vs A (%)")
    fig.suptitle("Frozen witness plans: 26 discrete model scenarios; no compiler speedup claim",fontsize=11)
    folder = ROOT/"figures"; folder.mkdir(exist_ok=True)
    fig.savefig(folder/"micro_witness_sensitivity.png",dpi=180)
    fig.savefig(folder/"micro_witness_sensitivity.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
