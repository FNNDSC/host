"""hostlib: run a program, stream its output, and keep the record.

Key components:
    - hostlib.models: the dataclasses every other package returns
    - hostlib.proc: job_run, job_start, JobHandle
    - hostlib.sink: where output goes while a job runs
    - hostlib.facts: what the host is

Dependencies:
    - standard library only
"""

from __future__ import annotations

__version__: str = "0.1.0"

__all__: list[str] = ["__version__"]
