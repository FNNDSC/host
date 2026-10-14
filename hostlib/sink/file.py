"""The sink that writes a job's record to files beside its results, live.

Four files share a prefix: ``<prefix>-cmd`` holds the command as run, written when
the job begins; ``<prefix>-stdout`` and ``<prefix>-stderr`` receive each chunk as it
arrives and are flushed per chunk, so a job that is killed still leaves what it
printed; ``<prefix>-returncode`` is written when the job ends. With ``rendered=True``
the two stream files are rewritten when the job ends as a terminal would have shown
them, each redrawn progress line reduced to its last frame; the record itself keeps
the raw text.

Key components:
    - FileSink: the sink
    - LOG_SUFFIXES: the four suffixes

Typical usage:
    sink = FileSink("/out/sub01/recon-all")
    result = job_run(spec, sink=sink)
    sink.logs  # JobLogs with the four paths

Dependencies:
    - hostlib.sink.protocol, hostlib.models
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TextIO

from hostlib.models.proc import JobLogs, JobResult
from hostlib.proc.render import terminal_render
from hostlib.sink.protocol import SinkBase

LOG_SUFFIXES: tuple[str, str, str, str] = ("cmd", "stdout", "stderr", "returncode")


class FileSink(SinkBase):
    """Write the job's record as four files sharing a prefix.

    Attributes:
        prefix: the path prefix; the parent directory is created when the job begins.
        rendered: rewrite the stream files at the end as a terminal would show them.
        logs: the four paths.

    Example:
        >>> FileSink("/out/job").logs.stdout
        '/out/job-stdout'
    """

    def __init__(self, prefix: str | Path, rendered: bool = False) -> None:
        self.prefix: Path = Path(prefix)
        self.rendered: bool = rendered
        self.logs: JobLogs = JobLogs(*(str(self.path_for(suffix)) for suffix in LOG_SUFFIXES))
        self.stdoutFile: TextIO | None = None
        self.stderrFile: TextIO | None = None

    def path_for(self, suffix: str) -> Path:
        """The path of one of the four files."""
        return self.prefix.with_name(f"{self.prefix.name}-{suffix}")

    def began(self, argv: list[str]) -> None:
        """Create the directory, write the command, open the two stream files."""
        self.prefix.parent.mkdir(parents=True, exist_ok=True)
        self.path_for("cmd").write_text(shlex.join(argv) + "\n")
        self.stdoutFile = self.path_for("stdout").open("w", newline="")
        self.stderrFile = self.path_for("stderr").open("w", newline="")

    def stdout_write(self, text: str) -> None:
        """Append the chunk to the stdout file and flush."""
        if self.stdoutFile is not None:
            self.stdoutFile.write(text)
            self.stdoutFile.flush()

    def stderr_write(self, text: str) -> None:
        """Append the chunk to the stderr file and flush."""
        if self.stderrFile is not None:
            self.stderrFile.write(text)
            self.stderrFile.flush()

    def ended(self, result: JobResult) -> None:
        """Close the stream files, render them if asked, and write the exit status."""
        for handle in (self.stdoutFile, self.stderrFile):
            if handle is not None:
                handle.close()
        self.stdoutFile = None
        self.stderrFile = None
        self.prefix.parent.mkdir(parents=True, exist_ok=True)
        if self.rendered:
            self.path_for("stdout").write_text(terminal_render(result.stdout), newline="")
            self.path_for("stderr").write_text(terminal_render(result.stderr), newline="")
        self.path_for("returncode").write_text(f"{result.returncode}\n")
