"""Task waiting categories are exclusive; they are NOT additive wall-clock stall cycles."""
from dataclasses import dataclass
import math


@dataclass
class Result:
    latency: float
    trace: list
    metrics: dict


def descriptor_size(task, fanin):
    """One hypothetical compact wire model, shared by byte admission and reporting."""
    return 48 + 5 * fanin + 8 * len(task.resources)


def cost(contract, hardware, policy, domains):
    n = len(contract.workload.tasks)
    e = len(contract.workload.edges)
    resources = len({r for t in contract.workload.tasks for r in t.resources})
    bits = max(1, math.ceil(math.log2(n + 1)))
    fanin = max((sum(x.consumer == t.tid for x in contract.workload.edges) for t in contract.workload.tasks), default=0)
    counter_bits = max(1, math.ceil(math.log2(fanin + 1)))
    entries = min(n, hardware.window * domains)
    dynamic = policy in {"B", "C"}
    descriptor = sum(descriptor_size(t, sum(x.consumer == t.tid for x in contract.workload.edges))
                     for t in contract.workload.tasks)
    # All policies need finite graph-event history for late admissions in this prototype.
    # Counts reflect actual simulator authority; no claim of O(window) total hardware state.
    history_bits = n + e
    order_bits = n * bits + sum(len(v) for v in contract.resource_order.values()) * bits
    edge_bits = max(1, math.ceil(math.log2(e + 1)))
    breakdown = {
        "completed_and_delivered_history": history_bits,
        "active_task_ids_status_dependency_counts": entries * (bits + counter_bits + 3),
        "resident_priority_hints": entries * 16,
        "ready_queue_ids": entries * bits if dynamic else domains * bits,
        "resource_busy_owner_ids": resources * (bits + 1),
        "completion_pending_ids_timestamps": entries * (bits + 32),
        "wakeup_pending_edge_task_ids_timestamps": e * (edge_bits + bits + 32),
        "issue_wakeup_port_timestamps": domains * (hardware.issue_width + hardware.wakeup_width) * 32,
        "order_and_admission_cursors": (resources + domains) * bits,
        "ready_age": entries * 32 if policy == "C" else 0,
    }
    return {"descriptor_bytes_estimate": descriptor,
            "dynamic_entries": entries if dynamic else 0,
            "abstract_state_bits": sum(breakdown.values()),
            "abstract_state_breakdown": breakdown,
            "state_accounting_status": "partial logical budget; queues provisioned to graph/window bounds; unknown decoder, routing, metadata caches, physical implementation",
            "persistent_event_history_bits": history_bits,
            "priority_comparators_upper": max(0, entries - domains) if dynamic else 0,
            "fanin_max": fanin, "dependency_edges": e,
            "resource_order_bytes": (order_bits + 7) // 8,
            "area_power_status": "partial abstract state/operation counts; neither RTL area/power nor a silicon upper bound"}
