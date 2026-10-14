"""host: run a program, stream its output, and keep the record.

Key components:
    - host.models: the dataclasses every other package returns
    - host.proc: job_run, job_start, JobHandle
    - host.sink: where output goes while a job runs
    - host.facts: what the host is

Dependencies:
    - standard library only
"""

from __future__ import annotations

__version__: str = "0.1.0"

__all__: list[str] = ["__version__"]
