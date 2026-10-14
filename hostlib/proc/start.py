"""Starting a job and holding on to it.

``job_start`` launches the program and returns a ``JobHandle`` at once. The handle's
reader threads drain both output pipes from the first moment, feeding the sink, so a
background job can never stall on a full pipe. ``wait`` and ``result`` turn the
handle into the same ``JobResult`` a foreground run returns, exactly once.

Key components:
    - job_start: launch, return a handle
    - JobHandle: pid, poll, wait, terminate, result, toRecord

Typical usage:
    handle = job_start(JobSpec(["sleep", "30"]), sink=FileSink("/out/run"))
    handle.poll()        # None while running
    handle.wait()        # the JobResult

Dependencies:
    - hostlib.models, hostlib.sink, hostlib.facts, hostlib.proc.streams
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import threading
import time

from hostlib.facts.facts import facts, timestamp_now
from hostlib.models.facts import HostFacts
from hostlib.models.proc import JobLogs, JobResult, JobSpec, JobStarted
from hostlib.proc.streams import StreamReader
from hostlib.sink.file import FileSink
from hostlib.sink.null import NullSink
from hostlib.sink.protocol import JobSink
from hostlib.sink.tee import TeeSink

TERMINATE_GRACE: float = 2.0


def environment_build(extra: dict[str, str] | None) -> dict[str, str] | None:
    """The caller's environment with ``extra`` laid over it; ``None`` when nothing is added."""
    if not extra:
        return None
    merged: dict[str, str] = dict(os.environ)
    merged.update(extra)
    return merged


def logs_find(sink: JobSink) -> JobLogs | None:
    """The file sink's log paths, if a file sink is attached directly or inside a tee."""
    if isinstance(sink, FileSink):
        return sink.logs
    if isinstance(sink, TeeSink):
        for inner in sink.sinks:
            found: JobLogs | None = logs_find(inner)
            if found is not None:
                return found
    return None


class JobHandle:
    """A running job.

    Attributes:
        spec: what was asked for.
        process: the process.
        sink: where its output goes.
        startedAt: when it started, ISO 8601.
        host: the host's facts at start.
        cwd: the working directory it runs in.

    Example:
        >>> handle = job_start(JobSpec(["true"]))
        >>> handle.wait().status
        True
    """

    def __init__(self, spec: JobSpec, process: subprocess.Popen[bytes], sink: JobSink, cwd: str) -> None:
        self.spec: JobSpec = spec
        self.process: subprocess.Popen[bytes] = process
        self.sink: JobSink = sink
        self.cwd: str = cwd
        self.startedAt: str = timestamp_now()
        self.startedClock: float = time.monotonic()
        self.host: HostFacts = facts(cwd)
        self.timedOut: bool = False
        self.resultRecord: JobResult | None = None
        self.resultLock: threading.Lock = threading.Lock()
        assert process.stdout is not None and process.stderr is not None
        self.stdoutReader: StreamReader = StreamReader(process.stdout, spec.encoding, sink.stdout_write)
        self.stderrReader: StreamReader = StreamReader(process.stderr, spec.encoding, sink.stderr_write)
        sink.began(list(spec.argv))
        self.stdoutReader.start()
        self.stderrReader.start()
        self.stdin_feed()

    def stdin_feed(self) -> None:
        """Write the spec's stdin text, if any, and close the pipe."""
        if self.process.stdin is None:
            return
        try:
            if self.spec.stdin is not None:
                self.process.stdin.write(self.spec.stdin.encode(self.spec.encoding))
        except BrokenPipeError:
            pass
        finally:
            with contextlib.suppress(BrokenPipeError):
                self.process.stdin.close()

    @property
    def pid(self) -> int:
        """The process id."""
        return self.process.pid

    def poll(self) -> int | None:
        """The exit status, or ``None`` while the program runs."""
        return self.process.poll()

    def wait(self, timeout: float | None = None) -> JobResult | None:
        """Wait for the program to exit.

        Args:
            timeout: seconds to wait; ``None`` waits forever.

        Returns:
            The record once it has exited; ``None`` if it is still running when the
            timeout elapses. Nothing is terminated here.
        """
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        return self.result()

    def terminate(self, grace: float = TERMINATE_GRACE) -> JobResult:
        """Stop the program: SIGTERM, then SIGKILL after ``grace`` seconds.

        Args:
            grace: seconds to wait between the two signals.

        Returns:
            The record, marked as timed out.
        """
        self.timedOut = True
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        result: JobResult | None = self.result()
        assert result is not None
        return result

    def result(self) -> JobResult | None:
        """The record, built once the program has exited and the pipes are drained.

        Returns:
            The record; ``None`` while the program is still running.
        """
        if self.process.poll() is None:
            return None
        with self.resultLock:
            if self.resultRecord is not None:
                return self.resultRecord
            self.stdoutReader.join()
            self.stderrReader.join()
            self.resultRecord = self.record_build()
            self.sink.ended(self.resultRecord)
            return self.resultRecord

    def record_build(self) -> JobResult:
        """Assemble the record from the exited process."""
        returncode: int = int(self.process.returncode)
        endedAt: str = timestamp_now()
        duration: float = time.monotonic() - self.startedClock
        errors: list[str] = []
        if self.timedOut:
            errors.append(f"timed out after {self.spec.timeout}s" if self.spec.timeout else "terminated")
        if returncode != 0 and not errors:
            errors.append(f"exit status {returncode}")
        return JobResult(
            status=returncode == 0 and not self.timedOut,
            argv=list(self.spec.argv),
            returncode=returncode,
            stdout=self.stdoutReader.text,
            stderr=self.stderrReader.text,
            errors=errors,
            host=self.host,
            startedAt=self.startedAt,
            endedAt=endedAt,
            duration=round(duration, 6),
            cwd=self.cwd,
            pid=self.process.pid,
            timedOut=self.timedOut,
        )

    def toRecord(self) -> JobStarted:
        """What a service tells a client about this running job."""
        return JobStarted(
            pid=self.process.pid,
            argv=list(self.spec.argv),
            cwd=self.cwd,
            startedAt=self.startedAt,
            host=self.host,
            logs=logs_find(self.sink),
        )


def job_start(spec: JobSpec, sink: JobSink | None = None) -> JobHandle:
    """Start the program and return a handle to it without waiting.

    Args:
        spec: what to run.
        sink: where its output goes while it runs; ``NullSink`` by default.

    Returns:
        The handle; its readers are already draining the output pipes.

    Raises:
        ValueError: ``spec.argv`` is empty.
        OSError: the program cannot be started (not found, not executable, bad cwd).
    """
    if not spec.argv:
        raise ValueError("argv is empty")
    cwd: str = os.path.abspath(spec.cwd) if spec.cwd else os.getcwd()
    process: subprocess.Popen[bytes] = subprocess.Popen(
        spec.argv,
        cwd=spec.cwd,
        env=environment_build(spec.env),
        stdin=subprocess.PIPE if spec.stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    return JobHandle(spec, process, sink if sink is not None else NullSink(), cwd)
