"""The facts of the host: where a program runs.

Key components:
    - HostFacts: hostname, user, pid, platform, cwd and the moment

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
