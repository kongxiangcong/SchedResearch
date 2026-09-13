"""ONNXim backend adapter, and an honest record of why it cannot run here.

There are two independent reasons this backend is not usable this round, and
they must not be collapsed into one another:

1. **Environment blocker** - the simulator cannot be built on this host. It is
   a C++20 CMake project that additionally needs conan plus five git
   submodules (onnx, protobuf, booksim, ramulator2, torch2timeloop). This host
   has no cmake, no conan, and PyPI is replaced by an HTML interception page,
   so none of those can be obtained. Details in
   ``configs/pinned_versions.json``.

2. **Capability blocker** - the source audit of the pinned commit shows the
   research capabilities this project needs are *not* present and would not be
   a small patch: every operator's output is written back to DRAM
   (``Core.cc``), the interconnect routes core<->DRAM only (``Simulator.cc``),
   and the simple scheduler imposes a whole-layer completion barrier
   (``Scheduler.cc``). Cross-operator residency and core-to-core exchange are
   therefore a redesign of execution, storage ownership and routing - which the
   round brief explicitly says must be recorded as a selection risk rather
   than hidden behind "future extensibility".

``OnnximBackend`` is therefore implemented as far as it honestly can be - it
resolves the binary, the config and the model list - and then *refuses* to
produce results instead of inventing them.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..repo import VENDOR_DIR

UPSTREAM_COMMIT = "a1e86296e080fa1c82f8ad3f1b6de1079c192afc"
SIMULATOR_BINARY = "build/bin/Simulator"
DEFAULT_CONFIG = "configs/systolic_ws_128x128_c4_simple_noc_tpuv4.json"
DEFAULT_MODELS = "example/models_list.json"


class BackendUnavailable(RuntimeError):
    """Raised when a backend cannot honestly produce a result."""


@dataclass
class BackendResult:
    backend: str
    executed: bool
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    blocker: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "executed": self.executed,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "blocker": self.blocker,
        }


# Capability verdicts taken from the source audit of the pinned commit.
# source = native | extension | unsupported | unknown
# verified = executed_pass | executed_fail | source_only | not_run
CAPABILITIES: dict[str, dict[str, str]] = {
    "tiling_and_loop_order": {"source": "native", "verified": "source_only",
                              "evidence": "Mapping.cc:25-49 reads an optional *.mapping file of [T]/[O]/[I] loop tuples"},
    "core_mapping_per_tile": {"source": "extension", "verified": "source_only",
                              "evidence": "Scheduler.cc:76-92 honours tile->core_id but nothing external can set it; only model-level target_core and config partiton_map exist (Common.h:124 defaults core_id=-1)"},
    "cross_operator_pipelining": {"source": "unsupported", "verified": "source_only",
                                  "evidence": "Scheduler.cc:207-209 issues the next layer only when every per-core queue is empty and count_active_layers()==0"},
    "same_core_cross_operator_residency": {"source": "unsupported", "verified": "source_only",
                                           "evidence": "Core.cc:36-74 flushes scratchpad per tile; accumulator preserved only within one fused op (Core.cc:54-58); outputs go back to DRAM"},
    "buffer_depth_and_capacity": {"source": "native", "verified": "source_only",
                                  "evidence": "Sram.cc:6-10 fixed capacity spad_size/2; overflow asserts (Sram.cc:48-50) or exits (Core.cc:338-342)"},
    "explicit_slot_reuse": {"source": "extension", "verified": "source_only",
                            "evidence": "AddressAllocator.h is an abstract base and is unused at runtime"},
    "core_to_core_communication": {"source": "unsupported", "verified": "source_only",
                                   "evidence": "Simulator.cc:269-275 routes every request to DRAM and every response to a core"},
    "dependency_and_resource_order": {"source": "native", "verified": "source_only",
                                      "evidence": "per-op tile dependencies plus the scheduler's ready handling"},
    "policy_replacement": {"source": "native", "verified": "source_only",
                           "evidence": "Scheduler::create factory (Scheduler.cc:4-20) selects a Scheduler subclass from config"},
    "dram_noc_backpressure": {"source": "native", "verified": "source_only",
                              "evidence": "booksim2/ramulator2 report is_full(); with icnt_type=simple, Interconnect.cc:63-66 always returns false, i.e. NO backpressure"},
    "self_timed_execution": {"source": "native", "verified": "source_only",
                             "evidence": "Simulator.cc:107-210 advances by actual tile completion, no global barrier"},
    "silu_swish": {"source": "native", "verified": "source_only",
                   "evidence": "BiasAct.cc:7 handles 'swish'; no standalone SiLU op"},
    "elementwise_multiply": {"source": "extension", "verified": "source_only",
                             "evidence": "Opcode::MUL only emitted inside the fused llama-MLP BiasAct (BiasAct.cc:126-134)"},
    "precision_cast": {"source": "unsupported", "verified": "source_only",
                       "evidence": "Cast maps to a Dummy no-op (OperationFactory.cc:48-49)"},
}


class OnnximBackend:
    """Adapter that resolves everything it can and refuses to fake the rest.

    ``execute`` is an **unimplemented execution adapter**: it refuses
    unconditionally. The historical capability audit below is preserved as
    evidence, but it is never wrapped as if an adapter existed.
    """

    name = "onnxim"
    upstream_commit = UPSTREAM_COMMIT
    patch_identity = None  # no patch was ever applied
    execution_adapter_implemented = False

    def __init__(self, vendor_dir: Path | None = None) -> None:
        self.vendor_dir = Path(vendor_dir) if vendor_dir else VENDOR_DIR / "ONNXim_git"

    def capabilities(self) -> dict[str, dict[str, str]]:
        return CAPABILITIES

    # -- what the audit can answer without a build ------------------------
    def source_audit(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "upstream_commit": self.upstream_commit,
            "execution_adapter_implemented": self.execution_adapter_implemented,
            "source_present": (self.vendor_dir / "src" / "Simulator.cc").is_file(),
            "config_present": (self.vendor_dir / DEFAULT_CONFIG).is_file(),
            "capabilities": CAPABILITIES,
        }

    # -- build/run gating --------------------------------------------------
    def binary(self) -> Path:
        return self.vendor_dir / SIMULATOR_BINARY

    def probe_environment(self) -> dict[str, Any]:
        """Live probe of *this* host, right now.

        Deliberately separate from the historical audit: if the host changes,
        these answers change, while the pinned-source capability findings do
        not.
        """
        import shutil

        return {
            "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "binary_expected": str(self.binary()),
            "binary_present": self.binary().is_file(),
            "cmake_on_path": shutil.which("cmake"),
            "conan_on_path": shutil.which("conan"),
            "source_tree_present": (self.vendor_dir / "src" / "Simulator.cc").is_file(),
        }

    def diagnose(self) -> dict[str, Any]:
        return {
            "environment_probe": self.probe_environment(),
            "historical_build_blockers_2026_09_09": [
                "cmake: absent on host and not obtainable (PyPI returns an HTML interception page)",
                "conan==1.57.0: absent and not installable",
                "git submodules onnx/protobuf/booksim/ramulator2: not fetchable through the truncating proxy",
                "gcc: available (MinGW), but C++20 + conan + cmake are all required",
            ],
            "capability_blockers_source_audit": [
                "cross-operator scratchpad residency is not supported (Core.cc)",
                "core-to-core data exchange is not supported (Simulator.cc)",
                "simple scheduler imposes a whole-layer completion barrier (Scheduler.cc)",
            ],
            "note": "capability blockers are pinned-source findings; the environment probe is live. "
                    "A different host does not change the source audit, and a new host is re-probed "
                    "rather than re-served the old machine's verdict.",
        }

    def execute(self, plan: Any, run_dir: Path) -> BackendResult:
        diagnosis = self.diagnose()
        raise BackendUnavailable(
            "ONNXim execution adapter is NOT IMPLEMENTED (and the simulator is "
            "absent here); refusing to fabricate a result. "
            + json.dumps(diagnosis, ensure_ascii=False)
        )
