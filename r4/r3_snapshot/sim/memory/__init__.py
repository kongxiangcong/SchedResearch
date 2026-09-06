"""Compiler-owned storage, with whole-buffer lifetime proofs (no numerical data)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Buffer:
    owner: str
    domain: str
    address: int
    size: int
    readers: tuple[str, ...]


def allocate(workload):
    next_address = {}
    result = []
    for t in workload.tasks:
        addr = next_address.get(t.domain, 0)
        size = ((t.output_bytes + 63) // 64) * 64
        readers = tuple(e.consumer for e in workload.edges
                        if e.producer == t.tid and e.kind == "data")
        result.append(Buffer(t.tid, t.domain, addr, size, readers))
        next_address[t.domain] = addr + size
    return tuple(result)


def validate_storage(buffers, reaches, capacity):
    for b in buffers:
        if not isinstance(b.address, int) or not isinstance(b.size, int) or b.address < 0 or b.address % 64 or b.size <= 0 or b.address + b.size > capacity:
            raise ValueError("invalid address/alignment or memory capacity exceeded")
    for i, a in enumerate(buffers):
        for b in buffers[i + 1:]:
            if a.domain != b.domain or max(a.address, b.address) >= min(a.address + a.size, b.address + b.size):
                continue
            def safely_before(earlier, later):
                return later.owner in reaches[earlier.owner] and all(
                    later.owner in reaches[r] for r in earlier.readers)
            if not (safely_before(a, b) or safely_before(b, a)):
                raise ValueError("unsafe alias: writer and all readers must precede next writer")
