# R11 independent audit

Status: PASS. Replayed 122 held-out traces (both variants), rebuilt service/FIFO/blackout timing and source traffic independently.

Quiet gain: -0.015670637%. A mean/95% CI: -0.599174254% [-0.610049107, -0.588299402]. B mean/95% CI: -0.605967308% [-0.617565500, -0.594369116].

The preregistered prefill gate recomputes to FAIL; decode is excluded because strict output-visible/clobber boundaries make the two static graphs identical.

The checker did not import runner graph/timing functions. It checked nonnegative causal dependencies, every resource FIFO predecessor, non-overlapping VMEM allocations, source-derived state/dense-MAC totals, all trace timestamps, blackout integration, lower bounds, and paired seed alignment.
