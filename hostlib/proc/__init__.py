"""hostlib.proc: running things.

Key components:
    - job_run: run to completion, return the record
    - job_start, JobHandle: start and hold a background job
    - argv_fromTemplate, argv_join: command lines as text
"""

from __future__ import annotations

from hostlib.proc.argv import argv_fromTemplate, argv_join
from hostlib.proc.run import job_run
from hostlib.proc.start import JobHandle, job_start

__all__: list[str] = ["JobHandle", "argv_fromTemplate", "argv_join", "job_run", "job_start"]
