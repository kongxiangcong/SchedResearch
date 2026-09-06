"""Synthetic service times. Contention emerges separately from resource exclusion."""
import hashlib
import math
import random


def sample(workload, seed, cov=0.0, tail_probability=0.0, tail_multiplier=4.0,
           vary=("memory", "communication")):
    result = {}
    for t in workload.tasks:
        # A grain sweep must not accidentally average away uncertainty by drawing
        # independent noise for fragments of the same coarse task.
        parent, marker, suffix = t.tid.rpartition(".tile")
        identity = parent if marker and suffix.isdecimal() else t.tid
        digest = hashlib.sha256(f"{seed}:{identity}".encode()).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        factor = 1.0
        if t.kind in vary:
            if cov:
                sigma = math.sqrt(math.log1p(cov * cov))
                factor = rng.lognormvariate(-sigma * sigma / 2, sigma)
            if rng.random() < tail_probability:
                factor *= tail_multiplier
        result[t.tid] = t.predicted * factor
    return result
