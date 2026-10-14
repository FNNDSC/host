"""What the host is.

Key components:
    - facts: the host's facts at this moment
    - timestamp_now: the moment, ISO 8601 with offset

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
import socket
from datetime import datetime

from hostlib.models.facts import HostFacts


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
