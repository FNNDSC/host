"""The sink that draws a progress bar on one terminal line.

A bar sink listens to the two channels the library itself never writes, ``status_write``
and ``progress_write``, which a caller running many jobs emits between them, and ignores
the output streams. Pair it in a ``TeeSink`` with a ``FileSink`` to keep the jobs' output,
or with a ``ConsoleSink`` to see it scroll under the bar.

Key components:
    - BarSink: the sink
    - BAR_WIDTH: the default width

Typical usage:
    sink = BarSink()
    for index, (name, spec) in enumerate(jobs.items(), start=1):
        sink.status_write(f"running {name}")
        job_run(spec, sink=sink)
        sink.progress_write(ProgressEvent("running", current=index, total=len(jobs)))
    sink.progress_write(ProgressEvent("ended", current=len(jobs), total=len(jobs)))

Dependencies:
    - hostlib.sink.protocol, hostlib.models
"""

from __future__ import annotations

import sys
from typing import TextIO

from hostlib.models.sink import ProgressEvent
from hostlib.sink.protocol import SinkBase

BAR_WIDTH: int = 30
LABEL_ROOM: int = 60


class BarSink(SinkBase):
    """A progress bar redrawn in place on every status or progress event.

    Attributes:
        err: where the bar is drawn; the process's stderr by default.
        width: the bar's width in characters.
        label: the current status text, drawn after the bar.
        current: the last ``current`` seen.
        total: the last ``total`` seen.
        failed: how many events carried ``status="error"``.

    Example:
        >>> import io
        >>> out = io.StringIO()
        >>> sink = BarSink(err=out, width=4)
        >>> sink.progress_write(ProgressEvent("running", current=1, total=2))
        >>> out.getvalue().startswith("\\r[##..] 1/2")
        True
    """

    def __init__(self, err: TextIO | None = None, width: int = BAR_WIDTH) -> None:
        self.err: TextIO = err if err is not None else sys.stderr
        self.width: int = width
        self.label: str = ""
        self.current: int = 0
        self.total: int = 0
        self.failed: int = 0

    def status_write(self, text: str) -> None:
        """Take the text as the bar's label and redraw."""
        self.label = text.rstrip("\n")
        self.draw()

    def progress_write(self, event: ProgressEvent) -> None:
        """Advance the bar and redraw; an ``ended`` event finishes the line."""
        if event.current is not None:
            self.current = event.current
        if event.total is not None:
            self.total = event.total
        if event.status == "error":
            self.failed += 1
        self.draw()
        if event.phase == "ended":
            self.err.write("\n")
            self.err.flush()

    def render(self) -> str:
        """The bar as one line, without the carriage return."""
        filled: int = round(self.width * self.current / self.total) if self.total else 0
        bar: str = "#" * filled + "." * (self.width - filled)
        failed: str = f"  {self.failed} failed" if self.failed else ""
        return f"[{bar}] {self.current}/{self.total}{failed}  {self.label}"

    def draw(self) -> None:
        """Redraw the bar in place, padded so a shorter line covers a longer one."""
        self.err.write("\r" + self.render().ljust(self.width + LABEL_ROOM))
        self.err.flush()
