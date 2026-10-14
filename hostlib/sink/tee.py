"""The sink that fans out to several sinks."""

from __future__ import annotations

from hostlib.models.proc import JobResult
from hostlib.models.sink import ProgressEvent
from hostlib.sink.protocol import JobSink, SinkBase


class TeeSink(SinkBase):
    """Forward every hook to each sink in turn, in the order given.

    Attributes:
        sinks: the sinks.

    Example:
        >>> from hostlib.sink.null import NullSink
        >>> len(TeeSink(NullSink(), NullSink()).sinks)
        2
    """

    def __init__(self, *sinks: JobSink) -> None:
        self.sinks: tuple[JobSink, ...] = sinks

    def began(self, argv: list[str]) -> None:
        for sink in self.sinks:
            sink.began(argv)

    def stdout_write(self, text: str) -> None:
        for sink in self.sinks:
            sink.stdout_write(text)

    def stderr_write(self, text: str) -> None:
        for sink in self.sinks:
            sink.stderr_write(text)

    def status_write(self, text: str) -> None:
        for sink in self.sinks:
            sink.status_write(text)

    def progress_write(self, event: ProgressEvent) -> None:
        for sink in self.sinks:
            sink.progress_write(event)

    def ended(self, result: JobResult) -> None:
        for sink in self.sinks:
            sink.ended(result)
