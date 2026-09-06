from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Hardware:
    window: int = 256
    byte_window: int = 65536
    issue_width: int = 4
    issue_cycle: float = 0.0
    dispatch_latency: float = 0.0
    completion_latency: float = 0.0
    wakeup_width: int = 4
    wakeup_cycle: float = 0.0
    distributed: bool = False
    memory_capacity: int = 1 << 28

    def validate(self):
        if min(self.window, self.byte_window, self.issue_width, self.wakeup_width, self.memory_capacity) < 1:
            raise ValueError("hardware capacities must be positive")
        if any(not math.isfinite(x) or x < 0 for x in (
            self.issue_cycle, self.dispatch_latency, self.completion_latency, self.wakeup_cycle)):
            raise ValueError("hardware delays must be finite and nonnegative")

    def domain(self, task):
        return task.domain if self.distributed else "central"


class Ports:
    """Independent service lanes; each lane accepts at most one item per cycle."""
    def __init__(self, width, cycle):
        self.times = [0.0] * width
        self.cycle = cycle

    def next(self):
        return min(self.times)

    def reserve(self, now):
        i = min(range(len(self.times)), key=self.times.__getitem__)
        start = max(now, self.times[i])
        self.times[i] = start + self.cycle
        return start
