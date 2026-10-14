"""What a sink is: where a job's output goes while the job runs.

A sink sees the job begin, receives each chunk of each stream as it arrives, may
receive status lines and progress events, and sees the job end with its record.
``JobSink`` is the structural type; ``SinkBase`` is a do-nothing implementation to
subclass when only some of the hooks matter.

Key components:
    - JobSink: the protocol
    - SinkBase: every hook as a no-op

Dependencies:
    - hostlib.models
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hostlib.models.proc import JobResult
from hostlib.models.sink import ProgressEvent


@runtime_checkable
class JobSink(Protocol):
    """Where a job's output goes while it runs."""

    def began(self, argv: list[str]) -> None:
        """The job has started.

        Args:
            argv: the argument list that is executing.
        """

    def stdout_write(self, text: str) -> None:
        """A chunk of standard output has arrived.

        Args:
            text: the chunk, decoded; not necessarily a whole line.
        """

    def stderr_write(self, text: str) -> None:
        """A chunk of standard error has arrived.

        Args:
            text: the chunk, decoded; not necessarily a whole line.
        """

    def status_write(self, text: str) -> None:
        """An ephemeral status line, which a consumer may overwrite or drop.

        Args:
            text: the line.
        """

    def progress_write(self, event: ProgressEvent) -> None:
        """A progress report.

        Args:
            event: the report.
        """

    def ended(self, result: JobResult) -> None:
        """The job has ended.

        Args:
            result: its record.
        """


class SinkBase:
    """A sink that does nothing; subclass and override what matters.

    Example:
        >>> class Count(SinkBase):
        ...     n = 0
        ...     def stdout_write(self, text: str) -> None:
        ...         self.n += len(text)
        >>> isinstance(Count(), JobSink)
        True
    """

    def began(self, argv: list[str]) -> None:
        """The job has started."""

    def stdout_write(self, text: str) -> None:
        """A chunk of standard output has arrived."""

    def stderr_write(self, text: str) -> None:
        """A chunk of standard error has arrived."""

    def status_write(self, text: str) -> None:
        """An ephemeral status line."""

    def progress_write(self, event: ProgressEvent) -> None:
        """A progress report."""

    def ended(self, result: JobResult) -> None:
        """The job has ended."""
