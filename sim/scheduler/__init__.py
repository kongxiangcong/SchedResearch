"""Online policies consume compiler hints and bounded current state only."""


def rank(policy, tid, priority, age, pressure):
    if policy == "C":
        # Extra per-ready-task age and resource-pressure arithmetic; no actual duration oracle.
        scale = max(max(priority.values()) - min(priority.values()), 1.0)
        return priority[tid] + 0.15 * age + 0.05 * scale * pressure
    return priority[tid]
