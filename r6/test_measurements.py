"""Synthetic contract fixtures only. No fixture is hardware data or performance evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from validate_measurements import SCHEMA, STATIC_DIMENSIONS, canonical_hash, validate


def fixture(root):
    """A documentary-complete in-memory fixture; fixture=True always bars admission."""
    raw = root / "SYNTHETIC_FIXTURE.txt"
    raw.write_text("SYNTHETIC SCHEMA FIXTURE ONLY; NO HARDWARE EXECUTION.\n", encoding="utf-8")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    instrument = {"id": "fixture_counter", "definition": "Synthetic structural fixture, no physical counter",
                  "unit": "defined_per_observation", "clock_domain": "synthetic", "sampling_boundary": "start to final payload visible",
                  "wrap_handling": "synthetic no wrap", "multiplex_handling": "none", "reset_rule": "each fixture",
                  "bit_width": 64, "clock_sync": {"method": "synthetic same domain", "max_error_ns": 0}}
    data = {key + "_sha256": digest for key in ("semantic_workload", "binary", "layout", "input", "initial_state", "software")}
    data.update({key + "_artifact_id": "synthetic" for key in ("semantic_workload", "binary", "layout", "input", "initial_state", "software")})
    data.update({"frequency": {"configured_hz": {"npu": 1000}, "actual_tolerance_pct": 0},
                 "implementation": {"dtype": "SYNTHETIC", "kernels": ["fixture"], "shapes": [1], "compiler_options": [], "ops": 1,
                                    "output_acceptance": "Synthetic contract structure only"},
                 "memory": {"capacity_bytes": 1, "address_mapping": "synthetic", "residency_scope": "synthetic",
                            "alias_last_reader": "synthetic", "warm_cold_rule": "synthetic"}})
    plan = {"frozen_at": "2026-09-05T00:00:00+00:00", "net_improvement_threshold_pct": 5.0,
            "paired_ci_lower_bound_required_gt": 0, "min_test_pairs_per_condition_per_session": 30,
            "min_test_sessions": 2, "min_non_extreme_interference_conditions": 2,
            "isolated_max_regression_pct": 1.0, "ci_method": "Synthetic declaration: paired bootstrap within session; each session must pass",
            "seeds": {"pilot": [1], "train": [2], "validation": [3], "test": list(range(100, 160))}}
    conditions = [{"id": "isolated", "isolation": True, "extreme": False}]
    for name in ("moderate", "high"):
        conditions.append({"id": name, "isolation": False, "extreme": False, "master_id": "synthetic",
                           "program_sha256": digest, "input_sha256": digest, "read_write_ratio": [1, 1],
                           "address_range": "synthetic", "working_set_bytes": 1, "offered_bytes": 1, "phase_rule": "synthetic frozen seed"})
    comparisons = [{"id": "interference", "kind": "fixed_binary_interference", "baseline_contract_id": "static", "candidate_contract_id": "static"},
                   {"id": "recovery", "kind": "dynamic_recovery", "baseline_contract_id": "static", "candidate_contract_id": "static",
                    "intervention": {"policy_artifact_id": "synthetic", "causal_instrument_ids": ["fixture_counter"], "finite_state_bytes": 1,
                                     "control_latency_charged": True, "extra_traffic_charged": True, "frequency_effect_charged": True}}]
    strong = {"selected_contract_id": "static", "selected_on": "validation", "test_used_for_selection": False,
              "selection_artifact_id": "synthetic", "search_budget": "synthetic", "dimensions": {
                  dimension: {"status": "evaluated", "reason": "SYNTHETIC ONLY", "artifact_id": "synthetic"} for dimension in STATIC_DIMENSIONS}}
    calibration = {name: {"verified": True, "artifact_id": "synthetic"} for name in ("empty_run", "known_bytes_copy", "single_compute", "instrumentation_overhead")}
    calibration["overhead_charged"] = True
    record = {"schema_version": SCHEMA, "purpose": "screening", "fixture": True,
              "evidence": {"level": "device", "target": "SYNTHETIC SCHEMA FIXTURE, NOT A DEVICE", "physical_npu_confirmed": True,
                           "execution_confirmed": True, "limitations": ["Boolean fields exercised solely for schema testing; no hardware execution"]},
              "artifacts": [{"id": "synthetic", "path": raw.name, "sha256": digest}], "instrumentation": [instrument],
              "contracts": [{"id": "static", "sha256": canonical_hash(data), "data": data}],
              "preregistration": {"sha256": canonical_hash(plan), "data": plan}, "conditions": conditions,
              "comparisons": comparisons, "strong_static": strong, "calibration": calibration, "runs": []}

    def obs(value):
        return {"value": value, "instrument_id": "fixture_counter"}

    port = {"id": "synthetic"}
    port.update({direction + "_" + stage + "_bytes": 1 for direction in ("read", "write") for stage in ("requested", "accepted", "completed")})
    for cid, condition_names in (("interference", ("moderate", "high")), ("recovery", ("isolated", "moderate", "high"))):
        for condition in condition_names:
            for session in range(2):
                for block in range(30):
                    for arm_index, arm in enumerate(("baseline", "candidate")):
                        record["runs"].append({"id": f"{cid}-{condition}-{session}-{block}-{arm}", "status": "completed",
                            "numerical_pass": True, "raw_artifact_id": "synthetic", "contract_id": "static", "comparison_id": cid,
                            "condition_id": "isolated" if cid == "interference" and arm == "baseline" else condition,
                            "session_id": f"session-{session}", "split": "test", "phase_seed": 100 + session * 30 + block,
                            "pair_id": f"{cid}-{condition}-{block}", "arm": arm, "pair_order": (block + arm_index) % 2,
                            "captured_at": "2026-09-05T01:00:00+00:00", "metrics": {
                                "elapsed_device_ns": obs(100), "elapsed_host_ns": obs(101), "traffic": obs({"ports": [copy.deepcopy(port)]}),
                                "compute_active": obs({"engines": [{"id": "synthetic", "active_cycles": 1, "elapsed_cycles": 2}]}),
                                "request_observation": obs({"kind": "limit", "boundary_definition": "Synthetic accepted to visible",
                                                            "counters": {"configured_limit": 1, "observed_peak": 1, "at_limit_cycles": 0}})},
                            "capture_quality": {"dropped_records": 0, "overflow_count": 0, "unhandled_wraps": 0},
                            "actual_frequency_hz": obs({"npu": 1000}),
                            "background_actual_bytes": obs(0 if condition == "isolated" or (cid == "interference" and arm == "baseline") else 1)})
    return record


class MeasurementChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r6_schema_fixture_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = fixture(self.root)

    def check(self):
        return validate(self.record, self.root)

    def test_complete_fixture_still_cannot_qualify(self):
        result = self.check()
        self.assertTrue(result["record_valid"], result["errors"])
        self.assertEqual(result["blockers"], ["fixture or unclassified provenance cannot qualify"])
        self.assertFalse(result["device_screening_eligible"])
        self.assertFalse(result["mechanism_gate_eligible"])
        self.assertFalse(result["performance_gate_evaluated"])

    def test_artifact_tampering_rejected(self):
        (self.root / "SYNTHETIC_FIXTURE.txt").write_text("Changed fixture", encoding="utf-8")
        self.assertTrue(any("SHA256 mismatch" in e for e in self.check()["errors"]))

    def test_contract_tampering_rejected(self):
        self.record["contracts"][0]["data"]["implementation"]["dtype"] = "changed"
        self.assertTrue(any("canonical SHA256 mismatch" in e for e in self.check()["errors"]))

    def test_unknown_observation_is_valid_but_ineligible(self):
        self.record["runs"][0]["metrics"]["traffic"] = {"value": None, "unknown_reason": "Counter unavailable on fixture"}
        self.record["runs"][1]["metrics"]["traffic"] = {"value": None, "unknown_reason": "Counter unavailable on fixture"}
        result = self.check()
        self.assertTrue(result["record_valid"], result["errors"])
        self.assertTrue(any("traffic: unavailable" in b for b in result["blockers"]))

    def test_unknown_requires_reason(self):
        self.record["runs"][0]["metrics"]["compute_active"] = {"value": None}
        self.assertTrue(any("null requires unknown_reason" in e for e in self.check()["errors"]))

    def test_zero_cannot_be_unknown(self):
        self.record["runs"][0]["metrics"]["elapsed_device_ns"] = {"value": 0, "unknown_reason": "unknown", "instrument_id": "fixture_counter"}
        self.assertFalse(self.check()["record_valid"])

    def test_mixed_binary_in_fixed_comparison_rejected(self):
        other = copy.deepcopy(self.record["contracts"][0])
        other["id"] = "changed"
        other["data"]["implementation"]["compiler_options"] = ["changed"]
        other["sha256"] = canonical_hash(other["data"])
        self.record["contracts"].append(other)
        self.record["comparisons"][0]["candidate_contract_id"] = "changed"
        self.assertTrue(any("requires identical full contract" in e for e in self.check()["errors"]))

    def test_compiler_can_change_implementation_but_not_semantics(self):
        comparison = self.record["comparisons"][0]
        comparison["kind"] = "compiler_variant"
        comparison["candidate_contract_id"] = "changed"
        other = copy.deepcopy(self.record["contracts"][0])
        other["id"] = "changed"
        other["data"]["implementation"]["compiler_options"] = ["synthetic different tiling"]
        other["sha256"] = canonical_hash(other["data"])
        self.record["contracts"].append(other)
        for index, run in enumerate(self.record["runs"]):
            if run["comparison_id"] == "interference":
                if run["arm"] == "candidate":
                    run["contract_id"] = "changed"
                else:
                    run["condition_id"] = self.record["runs"][index + 1]["condition_id"]
        self.assertTrue(self.check()["record_valid"], self.check()["errors"])
        other["data"]["semantic_workload_sha256"] = "0" * 64
        other["sha256"] = canonical_hash(other["data"])
        self.assertTrue(any("changed fixed semantic_workload" in e for e in self.check()["errors"]))

    def test_split_overlap_rejected(self):
        pre = self.record["preregistration"]
        pre["data"]["seeds"]["train"].append(100)
        pre["sha256"] = canonical_hash(pre["data"])
        self.assertTrue(any("split overlap" in e for e in self.check()["errors"]))

    def test_trace_overflow_blocks_eligibility_without_erasing_run(self):
        self.record["runs"][0]["capture_quality"]["overflow_count"] = 1
        result = self.check()
        self.assertTrue(result["record_valid"])
        self.assertTrue(any("overflow_count nonzero" in b for b in result["blockers"]))
        self.assertEqual(len(self.record["runs"]), 600)

    def test_cpu_sdk_and_rtl_never_qualify(self):
        for level in ("cpu", "functional_sdk", "rtl_config"):
            self.record["evidence"]["level"] = level
            self.assertIn("physical target device evidence required", self.check()["blockers"])

    def test_repeated_seed_cannot_inflate_independent_blocks(self):
        self.record["runs"][2]["phase_seed"] = 100
        self.record["runs"][3]["phase_seed"] = 100
        self.assertTrue(any("duplicate independent phase seed" in e for e in self.check()["errors"]))

    def test_small_sample_and_single_session_blocked(self):
        self.record["runs"] = self.record["runs"][:20]
        result = self.check()
        self.assertTrue(any("fewer than 30 paired blocks" in b for b in result["blockers"]))
        self.assertTrue(any("fewer than two test sessions" in b for b in result["blockers"]))

    def test_one_extreme_profile_not_enough(self):
        self.record["conditions"][1]["extreme"] = True
        self.assertTrue(any("fewer than two non-extreme" in b for b in self.check()["blockers"]))

    def test_payload_change_is_not_dynamic_recovery(self):
        self.record["runs"][301]["metrics"]["traffic"]["value"]["ports"][0]["read_completed_bytes"] = 0
        self.assertTrue(any("completed payload bytes differ" in e for e in self.check()["errors"]))

    def test_preregistration_after_test_blocked(self):
        pre = self.record["preregistration"]
        pre["data"]["frozen_at"] = "2026-09-06T00:00:00+00:00"
        pre["sha256"] = canonical_hash(pre["data"])
        self.assertTrue(any("test predates preregistration" in b for b in self.check()["blockers"]))

    def test_unvaried_pair_order_blocked(self):
        for run in self.record["runs"]:
            run["pair_order"] = 0 if run["arm"] == "baseline" else 1
        self.assertTrue(any("pair execution order not varied" in b for b in self.check()["blockers"]))

    def test_frequency_drift_blocks(self):
        self.record["runs"][0]["actual_frequency_hz"]["value"]["npu"] = 900
        self.assertTrue(any("frequency outside frozen tolerance" in b for b in self.check()["blockers"]))

    def test_dynamic_must_use_selected_strong_static(self):
        other = copy.deepcopy(self.record["contracts"][0])
        other["id"] = "unchosen"
        self.record["contracts"].append(other)
        comparison = self.record["comparisons"][1]
        comparison["baseline_contract_id"] = comparison["candidate_contract_id"] = "unchosen"
        for run in self.record["runs"]:
            if run["comparison_id"] == "recovery":
                run["contract_id"] = "unchosen"
        result = self.check()
        self.assertTrue(result["record_valid"], result["errors"])
        self.assertTrue(any("not the selected strong-static contract" in b for b in result["blockers"]))

    def test_dynamic_requires_selected_contract_residual_control(self):
        self.record["comparisons"][0]["kind"] = "compiler_variant"
        for index, run in enumerate(self.record["runs"]):
            if run["comparison_id"] == "interference" and run["arm"] == "baseline":
                run["condition_id"] = self.record["runs"][index + 1]["condition_id"]
        result = self.check()
        self.assertTrue(result["record_valid"], result["errors"])
        self.assertTrue(any("selected strong-static same-binary residual control missing" in b for b in result["blockers"]))

    def test_dynamic_requires_matching_residual_conditions(self):
        extra = copy.deepcopy(self.record["conditions"][1])
        extra["id"] = "other_profile"
        self.record["conditions"].append(extra)
        for run in self.record["runs"]:
            if run["comparison_id"] == "recovery" and run["condition_id"] == "moderate":
                run["condition_id"] = "other_profile"
        result = self.check()
        self.assertTrue(result["record_valid"], result["errors"])
        self.assertTrue(any("matching selected-static residual test condition missing" in b for b in result["blockers"]))

    def test_limit_must_be_observed_and_defined(self):
        self.record["runs"][0]["metrics"]["request_observation"]["value"]["counters"] = {"arbitrary_number": 0}
        self.assertTrue(any("limit needs configured_limit" in e for e in self.check()["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
