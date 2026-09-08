"""Independent integer-tick replay of the R13 v1 pure-data service contract.

This module deliberately imports neither the DES nor its builders. It advances
one tick at a time and keeps explicit queue, reservation and credit state.
Passing this replay establishes agreement of a declared model, not chip timing.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
from typing import Any


def simulate(spec: dict[str, Any], *, max_ticks: int = 5_000_000) -> dict[str, Any]:
    """Replay *spec* without sharing event advancement or costs with the DES.

    A bounded tick limit raises instead of returning a misleading finished run.
    The normal ``deadlock`` result is reserved for no remaining time-dependent
    condition capable of making progress.
    """
    buffers = deepcopy(spec.get("buffers", {}))
    groups = deepcopy(spec.get("groups", {}))
    jobs = {job["id"]: deepcopy(job) for job in spec.get("jobs", [])}
    if len(jobs) != len(spec.get("jobs", [])):
        raise ValueError("duplicate job id")
    reverse = spec.get("tie_break", "ascending") == "descending"
    if spec.get("tie_break", "ascending") not in ("ascending", "descending"):
        raise ValueError("unknown tie_break")

    queues: dict[str, list[tuple[int, str]]] = {name: [] for name in buffers}
    active_queues: set[str] = set()
    job_names = tuple(sorted(jobs))
    # Columns are distinct: physically reserved, occupied, and released but
    # upstream credit has not returned. The third is not physical occupancy.
    counts = {name: [0, 0, 0] for name in buffers}
    peaks = {name: 0 for name in buffers}
    last_service = {name: -1 for name in buffers}
    ready_at: dict[str, int] = {}
    owner: dict[str, Any] = {}
    launches: dict[str, int] = defaultdict(int)
    # 0=not admitted; 1=resident; 2=in flight; 3=finished.
    states = {name: 0 for name in jobs}
    stages = {name: 0 for name in jobs}
    completions: dict[int, list[tuple[str, int]]] = defaultdict(list)
    returns: dict[int, list[str]] = defaultdict(list)
    completed_ops: set[str] = set()
    end_times: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    pending_events = 0
    last_change = 0

    group_for: dict[str, str] = {}
    for group_id, group in groups.items():
        for queue_id in group["members"]:
            if queue_id not in queues:
                raise ValueError(f"unknown group member {queue_id}")
            if queue_id in group_for:
                raise ValueError(f"queue appears in multiple groups: {queue_id}")
            group_for[queue_id] = group_id
    all_op_ids = {f"{name}:{i}" for name, job in jobs.items()
                  for i in range(len(job["ops"]))}
    for name, buffer in buffers.items():
        cap = buffer.get("capacity")
        if cap is not None and (not isinstance(cap, int) or cap < 0):
            raise ValueError(f"invalid buffer capacity {name}")
        if buffer.get("credit_delay", 0) < 0:
            raise ValueError(f"negative credit delay {name}")
    for name, job in jobs.items():
        if not job["ops"]:
            raise ValueError(f"empty job {name}")
        if job.get("release", 0) < 0:
            raise ValueError(f"negative release {name}")
        if not set(job.get("deps", [])).issubset(all_op_ids):
            raise ValueError(f"unknown dependency in {name}")
        for operation in job["ops"]:
            if operation["queue"] not in queues:
                raise ValueError(f"unknown operation queue in {name}")
            if not isinstance(operation["latency"], int) or operation["latency"] < 0:
                raise ValueError("latency must be a nonnegative integer")
            if any(not isinstance(ii, int) or ii <= 0
                   for ii in operation.get("resources", {}).values()):
                raise ValueError("resource initiation intervals must be positive integers")

    def used(queue_id: str) -> int:
        return sum(counts[queue_id])

    def can_allocate(queue_id: str) -> bool:
        cap = buffers[queue_id].get("capacity")
        after = used(queue_id) + 1
        if cap is not None and after > cap:
            return False
        if queue_id in group_for:
            group = groups[group_for[queue_id]]
            if after > group["per_member"]:
                return False
            total = sum(max(used(member) + (member == queue_id)
                            - group["guaranteed"], 0)
                        for member in group["members"])
            if total > group["shared"]:
                return False
        return True

    def assert_state() -> None:
        for queue_id, state in counts.items():
            if min(state) < 0:
                raise AssertionError(("negative buffer state", queue_id, state))
            cap = buffers[queue_id].get("capacity")
            if cap is not None and sum(state) > cap:
                raise AssertionError(("buffer overflow", queue_id, state))
            if state[1] != len(queues[queue_id]):
                raise AssertionError(("resident count mismatch", queue_id))
            peaks[queue_id] = max(peaks[queue_id], sum(state))
        for group_id, group in groups.items():
            if any(used(member) > group["per_member"] for member in group["members"]):
                raise AssertionError(("VC limit", group_id))
            if sum(max(used(member) - group["guaranteed"], 0)
                   for member in group["members"]) > group["shared"]:
                raise AssertionError(("shared pool overflow", group_id))

    def enqueue(queue_id: str, name: str, now: int) -> None:
        counts[queue_id][1] += 1
        queues[queue_id].append((now, name))
        queues[queue_id].sort()
        active_queues.add(queue_id)
        states[name] = 1

    def apply_due(now: int) -> None:
        nonlocal pending_events, last_change
        # Batch every completion/return before collecting a new service winner.
        finished = completions.pop(now, [])
        credits = returns.pop(now, [])
        changed = bool(finished or credits)
        pending_events -= len(finished) + len(credits)
        for queue_id in credits:
            counts[queue_id][2] -= 1
        for name, index in sorted(finished):
            job = jobs[name]
            operation = job["ops"][index]
            completed_ops.add(f"{name}:{index}")
            lock = operation.get("lock")
            if lock and job.get("tail", False):
                if owner.get(lock) != job["packet"]:
                    raise AssertionError(("tail lost VC owner", name, lock))
                del owner[lock]
            if index + 1 < len(job["ops"]):
                next_queue = job["ops"][index + 1]["queue"]
                counts[next_queue][0] -= 1
                stages[name] = index + 1
                enqueue(next_queue, name, now)
            else:
                states[name] = 3
                end_times[name] = now
        if finished or credits:
            last_change = now
        # Initial admission always uses stable ascending IDs. Tie-break affects
        # arbitration, not initial visibility or queue FIFO arrival order.
        for name in job_names:
            job = jobs[name]
            if (states[name] == 0 and job.get("release", 0) <= now
                    and all(dep in completed_ops for dep in job.get("deps", []))):
                queue_id = job["ops"][0]["queue"]
                if can_allocate(queue_id):
                    enqueue(queue_id, name, now)
                    last_change = now
                    changed = True
        if changed:
            assert_state()

    def select(now: int) -> tuple[str, str] | None:
        candidates: list[tuple[int, str, str]] = []
        for queue_id in active_queues:
            entries = queues[queue_id]
            name = entries[0][1]
            job = jobs[name]
            index = stages[name]
            operation = job["ops"][index]
            if any(ready_at.get(resource, 0) > now
                   for resource in operation.get("resources", {})):
                continue
            if index + 1 < len(job["ops"]):
                if not can_allocate(job["ops"][index + 1]["queue"]):
                    continue
            lock = operation.get("lock")
            if lock and lock in owner and owner[lock] != job["packet"]:
                continue
            candidates.append((last_service[queue_id], queue_id, name))
        if not candidates:
            return None
        oldest = min(row[0] for row in candidates)
        ties = [(queue_id, name) for last, queue_id, name in candidates if last == oldest]
        return sorted(ties, reverse=reverse)[0]

    def start(queue_id: str, name: str, now: int) -> None:
        nonlocal pending_events, last_change
        job = jobs[name]
        index = stages[name]
        operation = job["ops"][index]
        entries = queues[queue_id]
        if entries.pop(0)[1] != name:
            raise AssertionError("FIFO selection changed")
        if not entries:
            active_queues.remove(queue_id)
        counts[queue_id][1] -= 1
        counts[queue_id][2] += 1
        credit_time = now + buffers[queue_id].get("credit_delay", 0)
        returns[credit_time].append(queue_id)
        pending_events += 1
        if index + 1 < len(job["ops"]):
            next_queue = job["ops"][index + 1]["queue"]
            counts[next_queue][0] += 1
        resources = operation.get("resources", {})
        for resource, interval in resources.items():
            ready_at[resource] = now + interval
            launches[resource] += 1
        lock = operation.get("lock")
        if lock:
            owner[lock] = job["packet"]
        finish = now + operation["latency"]
        completions[finish].append((name, index))
        pending_events += 1
        states[name] = 2
        records.append({"id": f"{name}:{index}", "start": now, "end": finish,
                        "queue": queue_id, "resources": deepcopy(resources), "lock": lock})
        last_service[queue_id] = now
        last_change = now
        assert_state()

    status = "ok"
    waiting: dict[str, Any] = {}
    for now in range(max_ticks + 1):
        apply_due(now)
        while True:
            chosen = select(now)
            if chosen is None:
                break
            start(*chosen, now)
            # Especially important for zero-latency logic and zero-delay credit.
            # It also admits newly enabled dependency jobs before arbitration.
            apply_due(now)
        if all(state == 3 for state in states.values()) and pending_events == 0:
            if owner:
                status = "deadlock"
                waiting = {"unreleased_locks": dict(owner)}
            break
        # A tick loop intentionally does not jump to these future times. This
        # check only distinguishes deadlock from a timed waiting condition.
        future = (pending_events > 0
                  or any(states[name] == 0 and job.get("release", 0) > now
                         for name, job in jobs.items())
                  or any(time > now for time in ready_at.values()))
        if not future:
            status = "deadlock"
            waiting = {"queues": {queue_id: [name for _, name in entries]
                                   for queue_id, entries in queues.items() if entries},
                       "not_admitted": [name for name, state in states.items() if state == 0],
                       "locks": dict(owner)}
            break
    else:
        raise TimeoutError(f"independent checker exceeded {max_ticks} integer ticks")

    return {"status": status, "operations": records, "job_end": end_times,
            "quiescent": last_change if status == "ok" else None,
            "stopped_at": now, "last_progress": last_change, "buffer_peaks": peaks,
            "resource_launches": dict(sorted(launches.items())), "waiting": waiting,
            "checker": "independent_integer_tick_v1"}


def compare_core(expected: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    """Return concrete differences, ignoring only operation list presentation order."""
    mismatches = []
    for label, output in (("expected", expected), ("actual", actual)):
        operation_ids = [row["id"] for row in output.get("operations", [])]
        if len(set(operation_ids)) != len(operation_ids):
            mismatches.append({"field": f"{label}.duplicate_operation_ids",
                               "expected": "each operation appears once", "actual": operation_ids})
    for key in ("status", "job_end", "quiescent", "buffer_peaks", "resource_launches"):
        if expected.get(key) != actual.get(key):
            mismatches.append({"field": key, "expected": expected.get(key), "actual": actual.get(key)})
    left = {row["id"]: {key: row.get(key) for key in ("start", "end", "queue", "resources", "lock")}
            for row in expected.get("operations", [])}
    right = {row["id"]: {key: row.get(key) for key in ("start", "end", "queue", "resources", "lock")}
             for row in actual.get("operations", [])}
    for operation_id in sorted(set(left) | set(right)):
        if left.get(operation_id) != right.get(operation_id):
            mismatches.append({"field": f"operations.{operation_id}",
                               "expected": left.get(operation_id), "actual": right.get(operation_id)})
    return mismatches


def audit_builder_rules(spec: dict[str, Any], hardware: dict[str, Any]) -> dict[str, Any]:
    """Independently derive route/flit and memory service from the registered model.

    Unlike simulate(), this does not trust the supplied operation costs. It
    derives them from packet endpoints, actual 16B block identities, and the
    registered parameter values. This still audits a scenario, not hardware.
    """
    metadata = spec["metadata"]
    params = metadata["params"]
    tags = metadata["tags"]
    jobs = {item["id"]: item for item in spec["jobs"]}
    packets = {item["id"]: item for item in metadata["packets"]}
    operations = {f"{name}:{i}": operation for name, item in jobs.items()
                  for i, operation in enumerate(item["ops"])}
    errors = []
    tick = hardware["ticks_per_cycle"]

    def expect(label, actual, expected):
        if actual != expected:
            errors.append({"check": label, "actual": actual, "expected": expected})

    def exact(number):
        value = Fraction(number)
        if value.denominator != 1:
            raise ValueError("registered service not representable in integer ticks")
        return int(value)

    def xy(point):
        return f"{point[0]},{point[1]}"

    def path_for(src, dst, noc, base_vc):
        # Modular-distance construction, independent of Builder.route's loop.
        links = [(f"link/{noc}/niu({xy(src)})->r({xy(src)})", 5 * tick, base_vc)]
        position = list(src)
        step = 1 if noc == 0 else -1
        for axis, modulus in ([(0, 10), (1, 12)] if noc == 0 else [(1, 12), (0, 10)]):
            count = ((dst[axis] - position[axis]) * step) % modulus
            origin = position[axis]
            for offset in range(1, count + 1):
                old = tuple(position)
                position[axis] = (origin + step * offset) % modulus
                wraps = origin + step * offset >= modulus or origin + step * offset < 0
                vc = base_vc + (8 if wraps else 0)
                links.append((f"link/{noc}/r({xy(old)})->r({xy(position)})", 9 * tick, vc))
        final_vc = links[-1][2]
        links.append((f"link/{noc}/r({xy(dst)})->niu({xy(dst)})", 5 * tick, final_vc))
        return links

    link_operations = memory_operations = memory_blocks = 0
    expected_link_launches: dict[str, int] = defaultdict(int)
    for name, packet in packets.items():
        role = packet["kind"]
        expected_class = {"read_request": 0, "write_request": 0,
                          "read_response": 3, "write_ack": 3, "notification": 1}[role]
        expect(f"{name}.class", packet["class"], expected_class)
        n_flits = 1 if role == "notification" else 1 + (packet["payload_bytes"] + 31) // 32
        expect(f"{name}.network_flits", packet["network_flits"], n_flits)
        path = path_for(packet["src"], packet["dst"], packet["noc"], expected_class << 1)
        expect(f"{name}.links", packet["links"], [link for link, _, _ in path])
        members = sorted([item for item in jobs.values() if item["packet"] == name],
                         key=lambda item: item["flit"])
        expect(f"{name}.flit_jobs", len(members), n_flits)
        for index, item in enumerate(members):
            expect(f"{item['id']}.flit", item["flit"], index)
            expect(f"{item['id']}.tail", item["tail"], index == n_flits - 1)
            supplied = [operation for operation in item["ops"]
                        if any(resource.startswith("link/") for resource in operation.get("resources", {}))]
            expect(f"{item['id']}.hop_count", len(supplied), len(path))
            for operation, (link, latency, vc) in zip(supplied, path):
                expect(f"{item['id']}.{link}.resource", operation["resources"], {link: tick})
                expect(f"{item['id']}.{link}.latency", operation["latency"], latency)
                expect(f"{item['id']}.{link}.vc", operation.get("lock"), f"{link}/vc{vc}")
                expected_link_launches[link] += 1
                link_operations += 1
        preparation = operations[f"{name}/prepare:0"]
        prep_ticks = exact(Fraction(str(params["niu_processing_cycles"])) * tick)
        expect(f"{name}.preparation_latency", preparation["latency"], prep_ticks)
        expect(f"{name}.preparation_resource", preparation["resources"],
               {f"niu_prepare/{xy(packet['src'])}/{packet['noc']}": prep_ticks} if prep_ticks else {})
        for direction, operation_ids in (("source", packet["read_ops"]),
                                          ("target", packet["write_ops"])):
            moved_blocks = [block for operation_id in operation_ids for block in tags[operation_id]["blocks"]]
            if role != "notification":
                expect(f"{name}.{direction}_bytes", 16 * len(moved_blocks), packet["payload_bytes"])
            endpoint = packet["src"] if direction == "source" else packet["dst"]
            for block in moved_blocks:
                parts = block.split("/")
                if parts[0] == "l1":
                    expect(f"{name}.{direction}_owner", parts[1], xy(endpoint))
                elif parts[0] == "dram":
                    group_ids = [i for i, coordinates in enumerate(hardware["dram_groups"])
                                 if list(endpoint) in coordinates]
                    expect(f"{name}.{direction}_controller_alias", [int(parts[1])], group_ids)

    for op_id, tag in tags.items():
        if tag.get("kind") == "signal":
            primitive = tag["primitive"]
            operation = operations[op_id]
            if primitive == "timer":
                cycles = Fraction(metadata["plan"]["chain1_offset_cycles"])
            elif primitive in hardware["control_cycles"]:
                cycles = Fraction(hardware["control_cycles"][primitive]) * Fraction(str(params["control_scale"]))
            else:
                cycles = Fraction(0)
            expect(f"{op_id}.primitive_latency", operation["latency"], exact(cycles * tick))
            if primitive == "timer":
                expect(f"{op_id}.timer_is_no_control_service", operation["resources"], {})
        blocks = tag.get("blocks")
        if not blocks:
            continue
        operation = operations[op_id]
        write = tag["kind"] in ("write", "compute_write")
        job_name = op_id.rsplit(":", 1)[0]
        packet = packets.get(jobs[job_name]["packet"])
        local = packet is None
        owners = {"/".join(block.split("/")[:-1]) for block in blocks}
        expect(f"{op_id}.one_memory_owner", len(owners), 1)
        owner = sorted(owners)[0]
        if owner.startswith("dram/"):
            byte_ticks = Fraction(16 * tick, 24) / Fraction(str(params["eta_d"]))
            offsets = [exact(byte_ticks * (index + 1)) for index in range(len(blocks))]
            expected_resources = {owner: offsets[-1]}
        else:
            tile = owner.split("/")[1]
            quantum = exact(Fraction(tick, 1) / (1 if local else Fraction(str(params["eta_n"]))))
            interface = "local" if local else f"noc{packet['noc']}"
            expected_resources = {f"l1_port/{tile}/{interface}/{'write' if write else 'read'}": quantum}
            occurrences: dict[int, int] = defaultdict(int)
            offsets = []
            for block in blocks:
                bank = 0 if metadata["bank_layout"] == "mono" else int(block.rsplit("/", 1)[1]) % 16
                occurrences[bank] += 1
                offsets.append(occurrences[bank] * quantum)
            for bank, count in occurrences.items():
                expected_resources[f"bank/{tile}/{bank}"] = count * quantum
        expect(f"{op_id}.service_resources", operation["resources"], expected_resources)
        expect(f"{op_id}.service_latency", operation["latency"], max(offsets))
        expect(f"{op_id}.block_completions", tag.get("block_completion_ticks"), offsets)
        memory_operations += 1
        memory_blocks += len(blocks)

    for group_id, group in spec["groups"].items():
        router = group_id.startswith("router_in/")
        capacity = 16 if router else params["niu_buffer_flits"]
        expect(f"{group_id}.members", len(group["members"]), 16)
        expect(f"{group_id}.guaranteed", group["guaranteed"], 1 if router else 0)
        expect(f"{group_id}.shared", group["shared"], 48 if router else capacity)
        expect(f"{group_id}.per_member", group["per_member"], capacity)
        for member in group["members"]:
            expect(f"{member}.capacity", spec["buffers"][member]["capacity"], capacity)
            expect(f"{member}.credit", spec["buffers"][member]["credit_delay"],
                   exact(Fraction(str(params["credit_cycles"])) * tick))

    return {"passed": not errors, "errors": errors, "packets": len(packets),
            "link_operations": link_operations, "memory_operations": memory_operations,
            "memory_16B_blocks": memory_blocks,
            "expected_link_launches": dict(sorted(expected_link_launches.items())),
            "scope": "independent modular routing, full packet-class flit ledger, registered 16B memory costs/offsets, and finite pool/credit constraints; no value/epoch replay"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = simulate(json.loads(arguments.spec.read_text(encoding="utf-8")))
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
