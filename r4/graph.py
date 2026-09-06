"""Small source graph interface. Numeric payloads are never scheduler inputs."""
from dataclasses import dataclass, field
from typing import Callable
import numpy as np


@dataclass
class Node:
    name: str
    engine: str  # MXU or VPU
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    run: Callable
    macs: int = 0
    vector_ops: int = 0
    source: str = ""
    fusion: str = ""
    core: int = 0


@dataclass
class Case:
    name: str
    initial: dict[str, np.ndarray]
    nodes: list[Node]
    outputs: tuple[str, ...]
    reference: dict[str, np.ndarray]
    metadata: dict = field(default_factory=dict)

    def evaluate(self, order=None):
        values = {k: v.copy() for k, v in self.initial.items()}
        nodes = {n.name: n for n in self.nodes}
        for name in order or [n.name for n in self.nodes]:
            n = nodes[name]
            result = n.run(*(values[k] for k in n.reads))
            if len(n.writes) == 1:
                result = (result,)
            if len(result) != len(n.writes):
                raise ValueError("output arity mismatch")
            for key, value in zip(n.writes, result):
                values[key] = np.asarray(value)
        return values
