"""Hand-derived state-machine fixtures, independent from DES implementation."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import unittest

from independent_checker import audit_builder_rules, compare_core, simulate


def queue(capacity=None, delay=0):
    return {"capacity": capacity, "credit_delay": delay}


def op(name, resource=None, ii=1, latency=1, lock=None):
    value = {"queue": name, "resources": {resource: ii} if resource else {}, "latency": latency}
    if lock:
        value["lock"] = lock
    return value


def job(name, ops, *, packet=None, tail=True, release=0, deps=()):
    return {"id": name, "packet": packet or name, "flit": 0, "tail": tail,
            "release": release, "deps": list(deps), "ops": ops}


def core_fixtures():
    """Named JSON fixtures reusable by the root runner for differential replay."""
    return {
        "one_hop_pipeline": {
            "buffers": {"input": queue(), "r0": queue(16, 648), "r1": queue(16, 648)},
            "jobs": [job(f"a{i}", [op("input", "in", 36, 180, "in-vc"),
                                   op("r0", "wire", 36, 324, "wire-vc"),
                                   op("r1", "out", 36, 180, "out-vc")],
                         packet="a", tail=i == 1) for i in range(2)]},
        "credit_roundtrip": {
            "buffers": {"input": queue(), "one": queue(1, 90)},
            "jobs": [job(f"a{i}", [op("input", "link", 1, 10),
                                   op("one", "sink", 1, 2)]) for i in range(2)]},
        "independent_crossing": {
            "buffers": {"left": queue(), "up": queue()},
            "jobs": [job("a", [op("left", "horizontal", 36, 324)]),
                     job("b", [op("up", "vertical", 36, 324)])]},
        "bank_conflict": {
            "buffers": {"noc0": queue(), "noc1": queue()},
            "jobs": [job("a", [op("noc0", "bank0", 36, 36)]),
                     job("b", [op("noc1", "bank0", 36, 36)])]},
        "channel_alias": {
            "buffers": {"endpoint0": queue(), "endpoint1": queue()},
            "jobs": [job("a", [op("endpoint0", "physical_channel", 64, 64)]),
                     job("b", [op("endpoint1", "physical_channel", 64, 64)])]},
        "zero_dependency": {
            "buffers": {"one": queue(), "two": queue()},
            "jobs": [job("a", [op("one", latency=0)]),
                     job("b", [op("two", latency=0)], deps=["a:0"])]},
        "shared_pool": {
            "buffers": {"vc0": queue(4, 30), "vc1": queue(4, 30)},
            "groups": {"port": {"members": ["vc0", "vc1"], "guaranteed": 1,
                                "shared": 1, "per_member": 4}},
            "jobs": [job(f"{vc}_{i}", [op(f"vc{vc}", "wire", 1, 10)])
                     for vc in range(2) for i in range(2)]},
        "same_vc_exclusion": {
            "buffers": {"qa": queue(), "qb": queue()},
            "jobs": [job("a0", [op("qa", "wire", 1, 10, "vc")], packet="a", tail=False),
                     job("a1", [op("qa", "wire", 1, 10, "vc")], packet="a", tail=True),
                     job("b0", [op("qb", "wire", 1, 10, "vc")], packet="b", tail=True)]},
        "different_vc_interleave": {
            "buffers": {"qa": queue(), "qb": queue()},
            "jobs": [job("a0", [op("qa", "wire", 1, 10, "vca")], packet="a", tail=False),
                     job("a1", [op("qa", "wire", 1, 10, "vca")], packet="a", tail=True),
                     job("b0", [op("qb", "wire", 1, 10, "vcb")], packet="b", tail=True)]},
    }


def differential_fixtures():
    """Fixed synthetic stress inputs, including deliberate resource deadlocks."""
    fixtures = core_fixtures()
    rng = random.Random(130901)
    for case in range(200):
        names = [f"q{i}" for i in range(rng.randint(2, 5))]
        spec = {"buffers": {q: queue(rng.randint(1, 4), rng.randint(0, 5)) for q in names},
                "jobs": [], "tie_break": rng.choice(["ascending", "descending"])}
        if case % 3 == 0:
            spec["groups"] = {"port": {"members": names, "guaranteed": 1,
                                       "shared": rng.randint(0, 5), "per_member": 4}}
        for ji in range(rng.randint(1, 8)):
            actions = []
            for _ in range(rng.randint(1, 4)):
                resources = {f"r{i}": rng.randint(1, 4)
                             for i in rng.sample(range(3), rng.randint(0, 2))}
                action = {"queue": rng.choice(names), "resources": resources,
                          "latency": rng.randint(0, 8)}
                if case % 4 == 0:
                    action["lock"] = f"lock{rng.randint(0, 1)}"
                actions.append(action)
            deps = []
            if ji > 0 and rng.random() < 0.2:
                before = rng.choice(spec["jobs"])
                deps = [f"{before['id']}:{len(before['ops']) - 1}"]
            spec["jobs"].append(job(f"j{ji:02}", actions, release=rng.randint(0, 8), deps=deps))
        fixtures[f"seed130901_{case:03}"] = spec
    return fixtures


def run_differential():
    # Only this test harness invokes the DES API. The independent engine imports
    # no DES or builders and was written before looking at their implementation.
    import event_machine
    root = Path(__file__).resolve().parent
    rows = []
    for name, spec in differential_fixtures().items():
        expected = simulate(spec, max_ticks=100000)
        actual = event_machine.simulate(spec)
        differences = compare_core(expected, actual)
        rows.append({"name": name,
                     "input_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
                     "status": expected["status"], "operations": len(expected["operations"]),
                     "quiescent": expected["quiescent"], "mismatches": differences})
    report = {"schema": "r13.independent-checker.differential.v1",
              "scope": "independent integer tick versus event-queue service engine; pure-data ops input",
              "command": "research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/test_independent_checker.py --differential",
              "seed": 130901, "random_cases": 200, "hand_cases": len(core_fixtures()),
              "passed": not any(row["mismatches"] for row in rows),
              "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in ("independent_checker.py", "test_independent_checker.py",
                                             "event_machine.py", "machine_contract.md")},
              "fixtures": rows,
              "interpretation": "fixed synthetic model implementation checks; no chip accuracy, performance gain, or complete DFG qualification claim"}
    destination = root / "artifacts" / "checker_differential.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "cases": len(rows),
                      "mismatch_cases": sum(bool(row["mismatches"]) for row in rows),
                      "deadlock_cases": sum(row["status"] == "deadlock" for row in rows)}, ensure_ascii=False))
    return report


def run_rule_mutations():
    """Check whether fixtures expose specific incorrect service-rule outputs."""
    import event_machine
    source = core_fixtures()
    mutations = []

    def add(name, fixture, edit):
        changed = deepcopy(source[fixture])
        edit(changed)
        mutations.append((name, source[fixture], changed))

    add("early_credit_return", "credit_roundtrip",
        lambda spec: spec["buffers"]["one"].update(credit_delay=0))
    add("erase_finite_reservation_limit", "credit_roundtrip",
        lambda spec: spec["buffers"]["one"].update(capacity=None))
    add("duplicate_channel_by_endpoint", "channel_alias",
        lambda spec: spec["jobs"][1]["ops"][0].update(resources={"alias_new_channel": 64}))
    add("duplicate_bank_by_noc", "bank_conflict",
        lambda spec: spec["jobs"][1]["ops"][0].update(resources={"bank0_on_noc1": 36}))
    add("erase_same_vc_exclusion", "same_vc_exclusion",
        lambda spec: [operation.pop("lock", None)
                      for item in spec["jobs"] for operation in item["ops"]])
    add("collapse_router_outputs", "independent_crossing",
        lambda spec: spec["jobs"][1]["ops"][0].update(resources={"horizontal": 36}))
    add("router_latency_equals_ii", "one_hop_pipeline",
        lambda spec: [item["ops"][1].update(latency=36) for item in spec["jobs"]])
    add("replicate_shared_pool", "shared_pool",
        lambda spec: spec.pop("groups"))
    rows = []
    for name, correct_spec, changed_spec in mutations:
        differences = compare_core(simulate(correct_spec), event_machine.simulate(changed_spec))
        rows.append({"name": name, "detected": bool(differences),
                     "differing_fields": [row["field"] for row in differences]})
    root = Path(__file__).resolve().parent
    report = {"schema": "r13.independent-checker.rule-mutations.v1",
              "command": "research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/test_independent_checker.py --mutations",
              "passed": all(row["detected"] for row in rows), "mutations": rows,
              "scope": "incorrect rule outputs are produced by changing DES input rules, then compared with independent replay of the original frozen rules; not source/target epoch mutations",
              "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in ("independent_checker.py", "test_independent_checker.py", "event_machine.py")}}
    (root / "artifacts" / "checker_rule_mutations.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "detected": sum(row["detected"] for row in rows),
                      "mutations": len(rows)}, ensure_ascii=False))
    return report


def run_unit_receipt():
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(IndependentCheckerTests))
    root = Path(__file__).resolve().parent
    report = {"schema": "r13.independent-checker.qualification.v1", "python": sys.version,
              "command": "research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/test_independent_checker.py --receipt",
              "tests_run": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "passed": result.wasSuccessful(),
              "scope": "independent state-machine fixtures; DES differential in separate receipt; not complete M0",
              "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in ("independent_checker.py", "test_independent_checker.py", "machine_contract.md")},
              "fixtures": {name: {key: value for key, value in simulate(spec).items()
                                   if key not in ("operations", "checker")}
                           for name, spec in core_fixtures().items()},
              "unverified_by_this_receipt": ["source/target DFG builder costs", "16B memory epoch audit",
                                              "real STREAM/TETRA admission", "full MLP and M1/M2"]}
    destination = root / "artifacts" / "checker_unit_receipt.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def run_builder_qualification():
    import event_machine
    from model_builder import HARDWARE, micro_graph, scenarios, small_plan_space
    root = Path(__file__).resolve().parent
    source_names = ("independent_checker.py", "test_independent_checker.py", "model_builder.py",
                    "event_machine.py", "hardware_model.json", "machine_contract.md")
    before = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_names}
    plans = small_plan_space()
    other = next(plan for plan in plans if plan["nocs"] == [1, 1, 1]
                 and plan["placement"] == "same_group_other_channel"
                 and plan["source_wait"] == "source" and plan["chain1_offset_cycles"] == 0)
    rows = []
    for name, plan, payload in (("micro64_noc1_other_channel", other, 64),
                                ("micro1024_noc0_alias", plans[0], 1024)):
        spec = micro_graph(plan, payload_bytes=payload)
        started = time.perf_counter()
        independent = simulate(spec, max_ticks=2_000_000)
        seconds = time.perf_counter() - started
        main = event_machine.simulate(spec)
        differences = compare_core(independent, main)
        rules = audit_builder_rules(spec, HARDWARE)
        actual_links = {key: value for key, value in main["resource_launches"].items() if key.startswith("link/")}
        ledger_match = actual_links == rules["expected_link_launches"]
        rows.append({"name": name, "plan": plan, "payload_bytes": payload,
                     "jobs": len(spec["jobs"]), "buffers": len(spec["buffers"]),
                     "independent_seconds": seconds, "status": independent["status"],
                     "quiescent": independent["quiescent"], "operations": len(independent["operations"]),
                     "mismatches": differences, "builder_rules": rules, "actual_link_ledger_matches": ledger_match,
                     "passed": not differences and rules["passed"] and ledger_match and independent["status"] == "ok"})
        print(json.dumps({key: rows[-1][key] for key in ("name", "passed", "independent_seconds", "quiescent")}), flush=True)
    matrix = []
    for layout in ("interleaved", "mono"):
        for i, params in enumerate(scenarios()):
            spec = micro_graph(other, params, payload_bytes=64, bank_layout=layout)
            rules = audit_builder_rules(spec, HARDWARE)
            matrix.append({"scenario_index": i, "params": params, "bank_layout": layout,
                           "passed": rules["passed"], "errors": rules["errors"]})
    after = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_names}
    report = {"schema": "r13.independent-checker.builder.v1",
              "command": "research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/test_independent_checker.py --micro",
              "source_hashes": before, "source_unchanged_during_run": before == after,
              "passed": before == after and all(row["passed"] for row in rows + matrix),
              "execution_cases": rows, "construction_only_service_checks": matrix,
              "scope": "full micro DFG service replay plus independently derived network and memory costs; matrix rows check construction only, not sensitivity performance, numerical values, M1, or M2"}
    (root / "artifacts" / "checker_builder.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "execution_cases": len(rows),
                      "construction_checks": len(matrix), "source_unchanged": before == after}))
    return report


class IndependentCheckerTests(unittest.TestCase):
    def check_fixture(self, name):
        result = simulate(core_fixtures()[name], max_ticks=5000)
        self.assertEqual(result["status"], "ok")
        return result, {item["id"]: item for item in result["operations"]}

    def test_one_hop_cut_through_hand_bound(self):
        result, rows = self.check_fixture("one_hop_pipeline")
        self.assertEqual(result["job_end"], {"a0": 684, "a1": 720})
        self.assertEqual(rows["a0:1"]["start"], 180)
        self.assertEqual(rows["a1:0"]["end"], 216)
        self.assertLess(rows["a0:1"]["start"], rows["a1:0"]["end"])
        self.assertEqual(result["quiescent"], 1188)

    def test_inflight_reservation_and_delayed_credit(self):
        result, rows = self.check_fixture("credit_roundtrip")
        self.assertEqual(rows["a1:0"]["start"], 100)
        self.assertEqual(result["buffer_peaks"]["one"], 1)
        self.assertEqual(result["job_end"]["a1"], 112)
        self.assertEqual(result["quiescent"], 200)

    def test_router_crossing_does_not_share_unrelated_outputs(self):
        _, rows = self.check_fixture("independent_crossing")
        self.assertEqual(rows["a:0"]["start"], rows["b:0"]["start"])

    def test_dual_noc_bank_conflict(self):
        _, rows = self.check_fixture("bank_conflict")
        self.assertEqual(rows["b:0"]["start"] - rows["a:0"]["start"], 36)

    def test_endpoint_alias_uses_one_channel(self):
        _, rows = self.check_fixture("channel_alias")
        self.assertEqual(rows["b:0"]["start"], 64)

    def test_zero_latency_fixed_point(self):
        result, rows = self.check_fixture("zero_dependency")
        self.assertEqual(rows["b:0"]["start"], 0)
        self.assertEqual(result["quiescent"], 0)

    def test_group_shared_pool_is_not_replicated(self):
        result, rows = self.check_fixture("shared_pool")
        self.assertEqual(result["buffer_peaks"], {"vc0": 2, "vc1": 2})
        # The fourth flit needs a returned shared credit, even though its own
        # VC's standalone capacity would have permitted admission immediately.
        self.assertGreaterEqual(rows["1_1:0"]["start"], 30)

    def test_same_vc_released_only_after_tail_propagation(self):
        _, rows = self.check_fixture("same_vc_exclusion")
        self.assertEqual(rows["a1:0"]["start"], 1)
        self.assertEqual(rows["b0:0"]["start"], 11)

    def test_different_vc_can_interleave(self):
        _, rows = self.check_fixture("different_vc_interleave")
        self.assertEqual(rows["b0:0"]["start"], 1)
        self.assertEqual(rows["a1:0"]["start"], 2)

    def test_input_container_order_is_not_arbitration(self):
        for fixture in core_fixtures().values():
            reordered = deepcopy(fixture)
            reordered["jobs"].reverse()
            reordered["buffers"] = dict(reversed(list(reordered["buffers"].items())))
            self.assertEqual(compare_core(simulate(fixture), simulate(reordered)), [])

    def test_descending_changes_only_same_age_winner(self):
        fixture = core_fixtures()["bank_conflict"]
        fixture["tie_break"] = "descending"
        result = simulate(fixture)
        rows = {row["id"]: row for row in result["operations"]}
        self.assertEqual(rows["b:0"]["start"], 0)
        self.assertEqual(rows["a:0"]["start"], 36)

    def test_dependency_cycle_is_deadlock(self):
        fixture = {"buffers": {"q": queue()}, "jobs": [
            job("a", [op("q")], deps=["b:0"]), job("b", [op("q")], deps=["a:0"])]}
        result = simulate(fixture)
        self.assertEqual(result["status"], "deadlock")
        self.assertIsNone(result["quiescent"])

    def test_missing_tail_does_not_claim_quiescence(self):
        fixture = {"buffers": {"q": queue()},
                   "jobs": [job("a", [op("q", "r", lock="vc")], tail=False)]}
        self.assertEqual(simulate(fixture)["status"], "deadlock")

    def test_core_comparison_rejects_early_completion(self):
        reference = simulate(core_fixtures()["credit_roundtrip"])
        broken = deepcopy(reference)
        broken["operations"][1]["end"] -= 1
        self.assertTrue(compare_core(reference, broken))

    def test_core_comparison_rejects_early_quiescence(self):
        reference = simulate(core_fixtures()["credit_roundtrip"])
        broken = deepcopy(reference)
        broken["quiescent"] = max(broken["job_end"].values())
        self.assertTrue(compare_core(reference, broken))

    def test_core_comparison_rejects_duplicate_operation(self):
        reference = simulate(core_fixtures()["credit_roundtrip"])
        broken = deepcopy(reference)
        broken["operations"].append(deepcopy(broken["operations"][0]))
        self.assertTrue(compare_core(reference, broken))

    def test_unknown_dependency_is_input_error(self):
        fixture = {"buffers": {"q": queue()}, "jobs": [job("a", [op("q")], deps=["missing:0"])]}
        with self.assertRaises(ValueError):
            simulate(fixture)


if __name__ == "__main__":
    if "--differential" in sys.argv:
        raise SystemExit(0 if run_differential()["passed"] else 1)
    if "--mutations" in sys.argv:
        raise SystemExit(0 if run_rule_mutations()["passed"] else 1)
    if "--receipt" in sys.argv:
        raise SystemExit(0 if run_unit_receipt()["passed"] else 1)
    if "--micro" in sys.argv:
        raise SystemExit(0 if run_builder_qualification()["passed"] else 1)
    unittest.main()
