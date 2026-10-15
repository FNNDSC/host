"""What the host is."""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

import pytest

from hostlib.facts import facts, memory_limit, memorySize_parse, timestamp_now, user_name
from hostlib.models import HostFacts, MemoryLimit


def test_facts_describeThisProcess() -> None:
    here: HostFacts = facts()
    assert here.hostname == socket.gethostname()
    assert here.pid == os.getpid()
    assert here.cwd == os.getcwd()
    assert here.platform
    assert here.user == user_name()


def test_facts_takesCwd() -> None:
    assert facts("/elsewhere").cwd == "/elsewhere"


def test_timestamp_isIsoWithOffset() -> None:
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", timestamp_now())


def procTree_make(root: Path, cgroupLines: str, availableKb: int | None) -> Path:
    proc: Path = root / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self" / "cgroup").write_text(cgroupLines)
    if availableKb is not None:
        (proc / "meminfo").write_text(f"MemTotal: 99999999 kB\nMemAvailable: {availableKb} kB\n")
    return proc


def test_memory_limit_cgroupV2_tightestUpTheHierarchy(tmp_path: Path) -> None:
    proc: Path = procTree_make(tmp_path, "0::/slurm/job_7/step_0\n", availableKb=64 * 2**20)
    cgroup: Path = tmp_path / "cgroup"
    (cgroup / "slurm/job_7/step_0").mkdir(parents=True)
    (cgroup / "slurm/job_7/step_0/memory.max").write_text("max\n")
    (cgroup / "slurm/job_7/memory.max").write_text(f"{48 * 2**30}\n")
    (cgroup / "slurm/memory.max").write_text(f"{100 * 2**30}\n")
    assert memory_limit(proc, cgroup) == MemoryLimit(48 * 2**30, "cgroup")


def test_memory_limit_containerRoot(tmp_path: Path) -> None:
    proc: Path = procTree_make(tmp_path, "0::/\n", availableKb=64 * 2**20)
    cgroup: Path = tmp_path / "cgroup"
    cgroup.mkdir()
    (cgroup / "memory.max").write_text(f"{32 * 2**30}\n")
    assert memory_limit(proc, cgroup) == MemoryLimit(32 * 2**30, "cgroup")


def test_memory_limit_cgroupV1(tmp_path: Path) -> None:
    proc: Path = procTree_make(tmp_path, "4:cpu,cpuacct:/x\n7:memory:/docker/abc\n", availableKb=64 * 2**20)
    limitDir: Path = tmp_path / "cgroup/memory/docker/abc"
    limitDir.mkdir(parents=True)
    (limitDir / "memory.limit_in_bytes").write_text(f"{8 * 2**30}\n")
    assert memory_limit(proc, tmp_path / "cgroup") == MemoryLimit(8 * 2**30, "cgroup")


def test_memory_limit_uncappedIsAvailableMemory(tmp_path: Path) -> None:
    proc: Path = procTree_make(tmp_path, "0::/user.slice\n", availableKb=20 * 2**20)
    cgroup: Path = tmp_path / "cgroup"
    (cgroup / "user.slice").mkdir(parents=True)
    (cgroup / "user.slice/memory.max").write_text("max\n")
    assert memory_limit(proc, cgroup) == MemoryLimit(20 * 2**30, "meminfo")


def test_memory_limit_capAboveAvailable_isAvailable(tmp_path: Path) -> None:
    proc: Path = procTree_make(tmp_path, "0::/\n", availableKb=10 * 2**20)
    cgroup: Path = tmp_path / "cgroup"
    cgroup.mkdir()
    (cgroup / "memory.max").write_text(f"{32 * 2**30}\n")
    assert memory_limit(proc, cgroup) == MemoryLimit(10 * 2**30, "meminfo")


def test_memory_limit_nothingReadable(tmp_path: Path) -> None:
    assert memory_limit(tmp_path / "noproc", tmp_path / "nocgroup") is None


def test_memorySize_parse() -> None:
    assert memorySize_parse("16Gi") == 16 * 2**30
    assert memorySize_parse("16GiB") == 16 * 2**30
    assert memorySize_parse("1.5G") == 1_500_000_000
    assert memorySize_parse("512Mi") == 512 * 2**20
    assert memorySize_parse("4096") == 4096
    with pytest.raises(ValueError):
        memorySize_parse("lots")
