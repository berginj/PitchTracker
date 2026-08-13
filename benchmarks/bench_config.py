"""Shared benchmark configuration and identity metadata.

Every benchmark result payload includes:
- ``benchmark_config``: parameters that controlled the run
- ``commit_identity``: git HEAD sha/dirty when available
- ``host_identity``: platform, Python version, CPU count
- ``raw_samples``: per-frame or per-interval measurements
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class HostIdentity:
    """Immutable snapshot of the execution host."""

    platform: str
    platform_version: str
    architecture: str
    python_version: str
    cpu_count: Optional[int]
    machine: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "platform_version": self.platform_version,
            "architecture": self.architecture,
            "python_version": self.python_version,
            "cpu_count": self.cpu_count,
            "machine": self.machine,
        }


@dataclass(frozen=True)
class CommitIdentity:
    """Git HEAD identity when available."""

    sha: Optional[str]
    dirty: Optional[bool]

    def to_dict(self) -> Dict[str, Any]:
        return {"sha": self.sha, "dirty": self.dirty}


@dataclass(frozen=True)
class BenchmarkConfig:
    """Immutable benchmark parameters included in every result."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, **self.params}


def get_host_identity() -> HostIdentity:
    return HostIdentity(
        platform=platform.system(),
        platform_version=platform.version(),
        architecture=platform.machine(),
        python_version=sys.version,
        cpu_count=os.cpu_count(),
        machine=platform.node(),
    )


def get_commit_identity() -> CommitIdentity:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty_output = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return CommitIdentity(sha=sha, dirty=bool(dirty_output))
    except Exception:
        return CommitIdentity(sha=None, dirty=None)


def build_result_envelope(
    *,
    benchmark_config: BenchmarkConfig,
    results: Dict[str, Any],
    raw_samples: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Wrap benchmark results with config, commit, and host identity."""
    envelope: Dict[str, Any] = {
        "benchmark_config": benchmark_config.to_dict(),
        "commit_identity": get_commit_identity().to_dict(),
        "host_identity": get_host_identity().to_dict(),
        "results": results,
    }
    if raw_samples is not None:
        envelope["raw_samples"] = raw_samples
    return envelope
