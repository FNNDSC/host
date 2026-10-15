"""What the host is.

Key components:
    - facts: the host's facts at this moment
    - timestamp_now: the moment, ISO 8601 with offset
    - memory_limit: the memory the process may use, from its control groups and
      the machine's available memory
    - memorySize_parse: a size as ChRIS and Kubernetes write it, ``16Gi``, in bytes

Typical usage:
    here = facts()
    print(here.hostname, here.user)

Dependencies:
    - hostlib.models.facts
"""

from __future__ import annotations

import getpass
import os
import platform
import re
import socket
from datetime import datetime
from pathlib import Path

from hostlib.models.facts import HostFacts, MemoryLimit

PROC_ROOT: Path = Path("/proc")
CGROUP_ROOT: Path = Path("/sys/fs/cgroup")
UNLIMITED_BYTES: int = 2**60
SIZE_UNITS: dict[str, int] = {
    "": 1,
    "k": 10**3,
    "m": 10**6,
    "g": 10**9,
    "t": 10**12,
    "ki": 2**10,
    "mi": 2**20,
    "gi": 2**30,
    "ti": 2**40,
}
SIZE_PATTERN: re.Pattern[str] = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmgt]i?)?b?\s*$", re.IGNORECASE)


def timestamp_now() -> str:
    """The current moment, ISO 8601 with the local offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def user_name() -> str:
    """The user the program runs as, or the empty string when the system cannot say."""
    try:
        return getpass.getuser()
    except (OSError, KeyError, ImportError):
        return ""


def facts(cwd: str | None = None) -> HostFacts:
    """The host's facts at this moment.

    Args:
        cwd: the working directory to record; ``None`` records the process's.

    Returns:
        Hostname, user, pid, platform, working directory and timestamp.
    """
    return HostFacts(
        hostname=socket.gethostname(),
        user=user_name(),
        pid=os.getpid(),
        platform=platform.platform(),
        cwd=cwd if cwd is not None else os.getcwd(),
        timestamp=timestamp_now(),
    )


def memorySize_parse(text: str) -> int:
    """A memory size as ChRIS, Kubernetes and Slurm write it, in bytes.

    ``Ki``, ``Mi``, ``Gi`` and ``Ti`` are powers of 1024; ``K``, ``M``, ``G`` and ``T``
    powers of 1000; a trailing ``B`` is allowed; a bare number is bytes.

    Raises:
        ValueError: text that is not a size.

    Example:
        >>> memorySize_parse("16Gi"), memorySize_parse("2G"), memorySize_parse("512")
        (17179869184, 2000000000, 512)
    """
    match: re.Match[str] | None = SIZE_PATTERN.match(text)
    if match is None:
        raise ValueError(f"not a memory size: {text!r}")
    return int(float(match.group(1)) * SIZE_UNITS[(match.group(2) or "").lower()])


def meminfo_available(procRoot: Path = PROC_ROOT) -> int | None:
    """The machine's available memory from ``/proc/meminfo``, in bytes; ``None`` when unreadable."""
    try:
        text: str = (procRoot / "meminfo").read_text()
    except OSError:
        return None
    match: re.Match[str] | None = re.search(r"^MemAvailable:\s+(\d+)\s*kB", text, re.MULTILINE)
    return int(match.group(1)) * 1024 if match else None


def limitFile_read(path: Path) -> int | None:
    """A cgroup limit file's value in bytes; ``None`` for ``max``, an absurd value or no file."""
    try:
        text: str = path.read_text().strip()
    except OSError:
        return None
    if not text.isdigit() or int(text) >= UNLIMITED_BYTES:
        return None
    return int(text)


def cgroup_limit(procRoot: Path = PROC_ROOT, cgroupRoot: Path = CGROUP_ROOT) -> int | None:
    """The tightest memory limit on this process's control groups, in bytes; ``None`` when uncapped.

    cgroup v2: the ``memory.max`` of the process's group and of every group above it
    up to the root, since a parent's limit binds a child. cgroup v1: the memory
    controller's ``memory.limit_in_bytes`` for the process's group. Inside a
    container the process's group is the namespace root, which these paths reach.
    """
    try:
        lines: list[str] = (procRoot / "self" / "cgroup").read_text().splitlines()
    except OSError:
        return None
    limits: list[int] = []
    for line in lines:
        parts: list[str] = line.split(":", 2)
        if len(parts) != 3:
            continue
        hierarchy, controllers, groupPath = parts
        if hierarchy == "0" and controllers == "":
            directory: Path = cgroupRoot / groupPath.lstrip("/")
            while True:
                found: int | None = limitFile_read(directory / "memory.max")
                if found is not None:
                    limits.append(found)
                if directory == cgroupRoot or cgroupRoot not in directory.parents:
                    break
                directory = directory.parent
        elif "memory" in controllers.split(","):
            found = limitFile_read(cgroupRoot / "memory" / groupPath.lstrip("/") / "memory.limit_in_bytes")
            if found is not None:
                limits.append(found)
    return min(limits) if limits else None


def memory_limit(procRoot: Path = PROC_ROOT, cgroupRoot: Path = CGROUP_ROOT) -> MemoryLimit | None:
    """The memory this process may use now: its control groups' limit or the machine's available memory.

    The smaller of the two wins, so a container's or a Slurm job's limit applies
    where it is the tighter, and an uncapped process on a busy machine is not
    promised memory that other programs hold.

    Args:
        procRoot: ``/proc``, replaced in tests.
        cgroupRoot: ``/sys/fs/cgroup``, replaced in tests.

    Returns:
        The limit and its source, or ``None`` when neither can be read, as off Linux.
    """
    capped: int | None = cgroup_limit(procRoot, cgroupRoot)
    available: int | None = meminfo_available(procRoot)
    if capped is not None and (available is None or capped < available):
        return MemoryLimit(bytes=capped, source="cgroup")
    if available is not None:
        return MemoryLimit(bytes=available, source="meminfo")
    return None
