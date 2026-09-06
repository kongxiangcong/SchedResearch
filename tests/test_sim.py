import unittest
from dataclasses import replace
from sim.workload import Task, Edge, Workload
from sim.workload.motifs import arrival_reversal, synthetic, tile
from sim.compiler import compile_candidates, select_static
from sim.execution import simulate, verify_trace
from sim.hardware_model import Hardware
from sim.hardware_model.latency import sample
from sim.scheduler.oracle import exact_orders


class SimulationTests(unittest.TestCase):
    def compile(self, workload):
        return select_static(compile_candidates(workload), Hardware())

    def test_deterministic_static_equals_scoreboard(self):
        for shape in ("chain", "fork_join", "pipeline", "llm_prefill", "dit_cfg"):
            c = self.compile(synthetic(shape))
            durations = sample(c.workload, 0)
            a, b = [simulate(c, Hardware(), durations, p) for p in ("A", "B")]
            self.assertAlmostEqual(a.latency, b.latency)
            verify_trace(c, b, Hardware())

    def test_bounded_nonalias_reversal_exact(self):
        c = self.compile(arrival_reversal())
        samples = [dict(load0=80, load1=120, vpu0=20, vpu1=20),
                   dict(load0=120, load1=80, vpu0=20, vpu1=20)]
        self.assertEqual(sum(simulate(c, Hardware(), d, "A").latency for d in samples) / 2, 150)
        for d in samples:
            self.assertEqual(simulate(c, Hardware(), d, "B").latency, 140)
            self.assertEqual(exact_orders(c, d)[0], 140)

    def test_common_random_numbers_are_task_identity_stable(self):
        w = synthetic("fork_join")
        shuffled = replace(w, tasks=tuple(reversed(w.tasks)))
        self.assertEqual(sample(w, 17, .6), sample(shuffled, 17, .6))
        self.assertNotEqual(sample(w, 17, .6), sample(w, 18, .6))

    def test_grain_sweep_preserves_parent_noise_and_work(self):
        w = synthetic("pipeline")
        d = sample(w, 19, .6)
        fine = sample(tile(w, 4), 19, .6)
        for tid in d:
            self.assertAlmostEqual(d[tid], sum(fine[f"{tid}.tile{i}"] for i in range(4)))

    def test_distributed_domains_match_real_topology(self):
        for clusters, chips in ((2, 1), (1, 2), (4, 1)):
            w = synthetic("pipeline", clusters=clusters, chips=chips)
            expected = {f"chip{chip}.cluster{cluster}" for chip in range(chips) for cluster in range(clusters)}
            self.assertEqual({t.domain for t in w.tasks}, expected)
        w = synthetic("dit_cfg")
        self.assertEqual({t.domain for t in w.tasks}, {"chip0.cluster0"})

    def test_tiling_keeps_sync_barriers(self):
        w = synthetic("pipeline", clusters=2, stages=2)
        kinds = {t.tid: t.kind for t in w.tasks}
        barrier_edges = [e for e in w.edges if kinds[e.producer] == "sync" or kinds[e.consumer] == "sync"]
        self.assertTrue(barrier_edges)
        self.assertTrue(all(e.kind == "completion" for e in barrier_edges))
        fine = tile(w, 2)
        pairs = {(e.producer, e.consumer) for e in fine.edges}
        for e in barrier_edges:
            for i in range(2):
                for j in range(2):
                    self.assertIn((f"{e.producer}.tile{i}", f"{e.consumer}.tile{j}"), pairs)

    def test_atomic_resources_and_visibility(self):
        c = self.compile(synthetic("llm_prefill", clusters=2))
        h = Hardware(window=5, byte_window=600, issue_width=1, issue_cycle=2,
                     dispatch_latency=2, completion_latency=3, wakeup_width=1, wakeup_cycle=4)
        for policy in ("A", "B", "C"):
            r = simulate(c, h, sample(c.workload, 13, .5), policy)
            verify_trace(c, r, h)
            self.assertLessEqual(r.metrics["window_peak"], 5)
            self.assertLessEqual(r.metrics["descriptor_bytes_peak"], 600)

    def test_all_simultaneous_completions_before_arbitration(self):
        w = Workload("tie", (Task("a", "compute", ("a",), 1), Task("b", "compute", ("b",), 1),
                     Task("x", "compute", ("v",), 1), Task("y", "compute", ("v",), 1)),
                     (Edge("a", "x"), Edge("b", "y")), "")
        c = replace(self.compile(w), priority={"a": 1, "b": 1, "x": 0, "y": 10})
        r = simulate(c, Hardware(), sample(w, 0), "B")
        starts = {x["task"]: x["start"] for x in r.trace}
        self.assertEqual(starts["y"], 1)
        self.assertEqual(starts["x"], 2)

    def test_wakeup_bandwidth(self):
        w = Workload("fanout", (Task("a", "compute", ("a",), 1), Task("b", "compute", ("b",), 1),
                     Task("c", "compute", ("c",), 1)), (Edge("a", "b"), Edge("a", "c")), "")
        c = self.compile(w)
        r = simulate(c, Hardware(wakeup_width=1, wakeup_cycle=5), sample(w, 0))
        self.assertEqual(r.latency, 7)
        self.assertEqual(r.metrics["wakeup_messages"], 2)

    def test_descriptor_byte_accounting_has_one_authority(self):
        from sim.metrics import descriptor_size
        c = self.compile(synthetic("pipeline"))
        r = simulate(c, Hardware(), sample(c.workload, 0))
        expected = sum(descriptor_size(t, sum(e.consumer == t.tid for e in c.workload.edges)) for t in c.workload.tasks)
        self.assertEqual(r.metrics["descriptor_bytes_estimate"], expected)
        self.assertEqual(r.metrics["abstract_state_bits"], sum(r.metrics["abstract_state_breakdown"].values()))

    def test_invalid_contracts_fail_closed(self):
        c = self.compile(arrival_reversal())
        with self.assertRaisesRegex(ValueError, "cycle"):
            bad = replace(c, workload=replace(c.workload, edges=c.workload.edges + (Edge("vpu0", "load0"),)))
            bad.validate(Hardware())
        with self.assertRaisesRegex(ValueError, "topological"):
            replace(c, admission_order=tuple(reversed(c.admission_order))).validate(Hardware())
        with self.assertRaisesRegex(ValueError, "byte admission"):
            simulate(c, Hardware(byte_window=8), sample(c.workload, 0))
        with self.assertRaisesRegex(ValueError, "service times"):
            simulate(c, Hardware(), {x: -1 for x in c.priority})
        with self.assertRaisesRegex(ValueError, "buffer size"):
            replace(c, buffers=(replace(c.buffers[0], size=1), *c.buffers[1:])).validate(Hardware())

    def test_static_admission_cannot_hide_required_resource_head(self):
        w = Workload("window", (Task("a", "compute", ("r",), 1),
                                Task("b", "compute", ("r",), 1)), (), "")
        c = self.compile(w)
        with self.assertRaisesRegex(ValueError, "bounded-window progress"):
            replace(c, admission_order=("a", "b"), resource_order={"r": ("b", "a")}).validate(Hardware(window=1))

    def test_address_reuse_requires_last_reader_and_writer_order(self):
        w = Workload("reuse", (Task("a", "compute", ("a",), 1), Task("r", "compute", ("r",), 1),
                     Task("b", "compute", ("b",), 1)), (Edge("a", "r"),), "")
        c = self.compile(w)
        buffers = tuple(replace(b, address=0) if b.owner == "b" else b for b in c.buffers)
        with self.assertRaisesRegex(ValueError, "unsafe alias"):
            replace(c, buffers=buffers).validate(Hardware())
        safe_w = replace(w, edges=w.edges + (Edge("r", "b", "WAR"), Edge("a", "b", "WAW")))
        safe = self.compile(safe_w)
        safe = replace(safe, buffers=tuple(replace(b, address=0) if b.owner == "b" else b for b in safe.buffers))
        safe.validate(Hardware())
        verify_trace(safe, simulate(safe, Hardware(), sample(safe_w, 0)), Hardware())

    def test_inconsistent_static_orders_reject_cycle(self):
        w = Workload("bundle", (Task("a", "compute", ("r", "s"), 1),
                                Task("b", "compute", ("r", "s"), 1)), (), "")
        c = self.compile(w)
        with self.assertRaisesRegex(ValueError, "cycle"):
            replace(c, resource_order={"r": ("a", "b"), "s": ("b", "a")}).validate(Hardware())


if __name__ == "__main__":
    unittest.main()
