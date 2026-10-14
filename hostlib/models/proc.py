"""The shapes of a job: what to run, what happened, what is running.

Key components:
    - JobSpec: the program to run and how
    - JobResult: the record of one completed run, the envelope
    - JobLogs: where a file sink wrote a job's record
    - JobStarted: the record of a job that is running

Dependencies:
    - hostlib.models.facts
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any

from hostlib.models.facts import HostFacts


@dataclass
class JobSpec:
    """A program to run.

    Attributes:
        argv: the program and its arguments, one list element each. Never a shell
            command line; use ``argv_fromTemplate`` to split one.
        cwd: the working directory to run in; ``None`` inherits the caller's.
        env: variables set on top of the caller's environment; ``None`` adds none.
        stdin: text written to the program's standard input, then closed; ``None``
            connects it to nothing.
        timeout: seconds ``job_run`` waits before terminating the program; ``None``
            waits forever.
        encoding: how the program's output bytes are decoded.

    Example:
        >>> JobSpec(["echo", "hi"]).argv
        ['echo', 'hi']
    """

    argv: list[str]
    cwd: str | None = None
    env: dict[str, str] | None = None
    stdin: str | None = None
    timeout: float | None = None
    encoding: str = "utf-8"


@dataclass
class JobLogs:
    """Where a file sink wrote a job's record.

    Attributes:
        cmd: the file holding the command as run.
        stdout: the file holding standard output.
        stderr: the file holding standard error.
        returncode: the file holding the exit status.
    """

    cmd: str
    stdout: str
    stderr: str
    returncode: str


@dataclass
class JobResult:
    """The record of one run: the envelope every run returns.

    ``status`` is the ground truth and is never inferred from the output text.

    Attributes:
        status: True when the program started and exited 0.
        argv: the argument list that was executed.
        returncode: the exit status; ``None`` when the program never started.
        stdout: the complete standard output, decoded.
        stderr: the complete standard error, decoded.
        errors: why a failed job failed, in words; empty on success.
        host: the facts of the host it ran on.
        startedAt: when it started, ISO 8601.
        endedAt: when it ended, ISO 8601.
        duration: seconds from start to end.
        cwd: the working directory it ran in.
        pid: the process id; ``None`` when the program never started.
        timedOut: True when ``timeout`` elapsed and the program was terminated.

    Example:
        >>> JobResult.failed(["x"], ["cannot run x"]).status
        False
    """

    status: bool
    argv: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    errors: list[str]
    host: HostFacts
    startedAt: str
    endedAt: str
    duration: float
    cwd: str
    pid: int | None
    timedOut: bool = False

    @classmethod
    def failed(
        cls,
        argv: list[str],
        errors: list[str],
        host: HostFacts | None = None,
        startedAt: str = "",
        cwd: str = "",
    ) -> JobResult:
        """A job that never ran.

        Args:
            argv: what would have run.
            errors: why it did not.
            host: the host's facts, when known.
            startedAt: when the attempt was made.
            cwd: where.

        Returns:
            A failed record with no output and no exit status.
        """
        facts: HostFacts = host if host is not None else HostFacts("", "", 0, "", cwd, startedAt)
        return cls(False, list(argv), None, "", "", list(errors), facts, startedAt, startedAt, 0.0, cwd, None)

    def toDict(self) -> dict[str, Any]:
        """The record as plain data, for JSON."""
        return dataclasses.asdict(self)

    def toJson(self, indent: int | None = 4) -> str:
        """The record as JSON text."""
        return json.dumps(self.toDict(), indent=indent, sort_keys=True)


@dataclass
class JobStarted:
    """The record of a job that is running: what a service tells a client.

    Attributes:
        pid: the process id.
        argv: the argument list that is executing.
        cwd: the working directory it runs in.
        startedAt: when it started, ISO 8601.
        host: the facts of the host it runs on.
        logs: where its record is being written, when a file sink is attached.
    """

    pid: int
    argv: list[str]
    cwd: str
    startedAt: str
    host: HostFacts
    logs: JobLogs | None = None
    errors: list[str] = field(default_factory=list)

    def toDict(self) -> dict[str, Any]:
        """The record as plain data, for JSON."""
        return dataclasses.asdict(self)
