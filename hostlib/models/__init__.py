"""hostlib.models: dataclasses only, one module per domain; stdlib imports only.

These are the shapes that cross a wire or land in a file. Nothing here has behaviour
beyond turning itself into plain data.
"""

from __future__ import annotations

from hostlib.models.facts import HostFacts, MemoryLimit
from hostlib.models.proc import JobLogs, JobResult, JobSpec, JobStarted
from hostlib.models.sink import ProgressEvent

__all__: list[str] = [
    "HostFacts",
    "JobLogs",
    "JobResult",
    "JobSpec",
    "JobStarted",
    "MemoryLimit",
    "ProgressEvent",
]
