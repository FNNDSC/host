"""The facts of the host: where a program runs.

Key components:
    - HostFacts: hostname, user, pid, platform, cwd and the moment
    - MemoryLimit: the memory the process may use, and where that figure came from

Dependencies:
    - standard library only
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HostFacts:
    """What the host is, at one moment.

    Attributes:
        hostname: the machine's name.
        user: the user the program runs as.
        pid: the program's process id.
        platform: the operating system, as ``platform.platform()`` names it.
        cwd: the working directory.
        timestamp: the moment, ISO 8601 with offset.

    Example:
        >>> HostFacts("box", "ann", 1, "Linux", "/", "2026-10-13T10:00:00+00:00").user
        'ann'
    """

    hostname: str
    user: str
    pid: int
    platform: str
    cwd: str
    timestamp: str


@dataclass
class MemoryLimit:
    """The memory this process may use, and where the figure came from.

    Attributes:
        bytes: the limit, in bytes.
        source: ``cgroup`` when a control group caps the process below what the
            machine has free, as a container's limit or a Slurm job's ``--mem``
            does; ``meminfo`` when the figure is the memory the machine has
            available now, uncapped or capped above it.

    Example:
        >>> MemoryLimit(32 * 2**30, "cgroup").gibibytes()
        32.0
    """

    bytes: int
    source: str

    def gibibytes(self) -> float:
        """The limit in GiB, for a message."""
        return self.bytes / 2**30
