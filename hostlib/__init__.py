"""hostlib: run a program, stream its output, and keep the record.

Key components:
    - job_run, job_start, JobHandle, terminal_render: running things (hostlib.proc)
    - JobSpec, JobResult, JobStarted, JobLogs, HostFacts, ProgressEvent: the shapes (hostlib.models)
    - JobSink and the shipped sinks: where output goes while a job runs (hostlib.sink)
    - facts: what the host is (hostlib.facts)

Typical usage:
    from hostlib import JobSpec, job_run
    result = job_run(JobSpec(["mri_convert", "in.dcm", "out.nii.gz"]))
    result.status, result.returncode, result.stdout

Dependencies:
    - standard library only
"""

from __future__ import annotations

from hostlib.facts.facts import facts
from hostlib.models.facts import HostFacts
from hostlib.models.proc import JobLogs, JobResult, JobSpec, JobStarted
from hostlib.models.sink import ProgressEvent
from hostlib.proc.argv import argv_fromTemplate, argv_join
from hostlib.proc.render import terminal_render
from hostlib.proc.run import job_run
from hostlib.proc.start import JobHandle, job_start
from hostlib.sink.protocol import JobSink, SinkBase

__version__: str = "1.0.0"

__all__: list[str] = [
    "HostFacts",
    "JobHandle",
    "JobLogs",
    "JobResult",
    "JobSink",
    "JobSpec",
    "JobStarted",
    "ProgressEvent",
    "SinkBase",
    "__version__",
    "argv_fromTemplate",
    "argv_join",
    "facts",
    "job_run",
    "job_start",
    "terminal_render",
]
