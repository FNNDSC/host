"""Running a job in the foreground.

``job_run`` is ``job_start`` followed by a wait, with the two ways a run can fail
before or without an exit status, a program that cannot start and a timeout, turned
into failed records rather than exceptions. It never raises for anything the program
does.

Key components:
    - job_run: start, stream, wait, record

Typical usage:
    result = job_run(JobSpec(["ls", "-l"]), sink=ConsoleSink())
    if not result.status: print(result.errors)

Dependencies:
    - hostlib.proc.start, hostlib.models, hostlib.facts
"""

from __future__ import annotations

import os

from hostlib.facts.facts import facts, timestamp_now
from hostlib.models.proc import JobResult, JobSpec
from hostlib.proc.start import JobHandle, job_start
from hostlib.sink.protocol import JobSink


def job_run(spec: JobSpec, sink: JobSink | None = None) -> JobResult:
    """Run the program to completion and return its record.

    Args:
        spec: what to run; ``spec.timeout`` bounds the wait.
        sink: where its output goes while it runs; ``NullSink`` by default.

    Returns:
        The record. A program that cannot be started is a failed record with no exit
        status; a program that outlives ``spec.timeout`` is terminated and its record
        marked ``timedOut``.

    Example:
        >>> job_run(JobSpec(["printf", "hi"])).stdout
        'hi'
    """
    cwd: str = os.path.abspath(spec.cwd) if spec.cwd else os.getcwd()
    startedAt: str = timestamp_now()
    if not spec.argv:
        return JobResult.failed([], ["argv is empty"], facts(cwd), startedAt, cwd)
    try:
        handle: JobHandle = job_start(spec, sink)
    except OSError as err:
        reason: str = err.strerror or str(err)
        return JobResult.failed(
            list(spec.argv), [f"cannot run {spec.argv[0]}: {reason}"], facts(cwd), startedAt, cwd
        )
    result: JobResult | None = handle.wait(spec.timeout)
    if result is None:
        result = handle.terminate()
    return result
