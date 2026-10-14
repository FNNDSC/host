"""The sink that streams a job's output to a terminal as it arrives.

Key components:
    - ConsoleSink: stdout to one text stream, stderr to another, flushed per chunk

Dependencies:
    - hostlib.sink.protocol
"""

from __future__ import annotations

import sys
from typing import TextIO

from hostlib.models.sink import ProgressEvent
from hostlib.sink.protocol import SinkBase


class ConsoleSink(SinkBase):
    """Stream the job's two output streams to two text streams, live.

    Attributes:
        out: where standard output goes; the process's stdout by default.
        err: where standard error and status lines go; the process's stderr by default.
        progress: write progress events to ``err`` as one line each.

    Example:
        >>> import io
        >>> buffer = io.StringIO()
        >>> sink = ConsoleSink(out=buffer)
        >>> sink.stdout_write("hello\\n")
        >>> buffer.getvalue()
        'hello\\n'
    """

    def __init__(self, out: TextIO | None = None, err: TextIO | None = None, progress: bool = True) -> None:
        self.out: TextIO = out if out is not None else sys.stdout
        self.err: TextIO = err if err is not None else sys.stderr
        self.progress: bool = progress

    def stdout_write(self, text: str) -> None:
        """Write the chunk to ``out`` and flush."""
        self.out.write(text)
        self.out.flush()

    def stderr_write(self, text: str) -> None:
        """Write the chunk to ``err`` and flush."""
        self.err.write(text)
        self.err.flush()

    def status_write(self, text: str) -> None:
        """Write the status line to ``err``."""
        self.err.write(text.rstrip("\n") + "\n")
        self.err.flush()

    def progress_write(self, event: ProgressEvent) -> None:
        """Write the event to ``err`` as one line, when ``progress`` is set."""
        if not self.progress:
            return
        parts: list[str] = [event.phase]
        if event.label:
            parts.append(event.label)
        if event.current is not None and event.total is not None:
            parts.append(f"{event.current}/{event.total}{(' ' + event.unit) if event.unit else ''}")
        elif event.percent is not None:
            parts.append(f"{event.percent:.0f}%")
        if event.status:
            parts.append(f"[{event.status}]")
        self.err.write(" ".join(parts) + "\n")
        self.err.flush()
