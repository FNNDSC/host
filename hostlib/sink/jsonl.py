"""The sink that appends a job's record as one line of JSON.

One line per job, the whole ``JobResult`` with sorted keys and no indentation: the
command, both streams complete and raw, the exit status, the errors, the host, the
timing. A file of such lines is read by ``pflog read``, by any log collector, and by
``json.loads`` a line at a time. The directory is created on first use and the file
is opened per job, so a crash between jobs loses nothing and several jobs in sequence
share one file.

Key components:
    - JsonSink: the sink
    - JOBS_FILE: the conventional file name, ``jobs.jsonl``
    - line_render: the line

Typical usage:
    sink = JsonSink(outputDir / "jobs.jsonl")
    for spec in specs:
        job_run(spec, sink=sink)

Dependencies:
    - hostlib.sink.protocol, hostlib.models
"""

from __future__ import annotations

from pathlib import Path

from hostlib.models.proc import JobResult
from hostlib.sink.protocol import SinkBase

JOBS_FILE: str = "jobs.jsonl"


def line_render(result: JobResult) -> str:
    """The record as one line of JSON, newline-terminated."""
    return result.toJson(indent=None) + "\n"


class JsonSink(SinkBase):
    """Append each ended job's record to a file as one line of JSON.

    Attributes:
        path: the file; its directory is created when the first job ends.

    Example:
        >>> JsonSink("/out/sub01/jobs.jsonl").path.name
        'jobs.jsonl'
    """

    def __init__(self, path: str | Path) -> None:
        self.path: Path = Path(path)

    def ended(self, result: JobResult) -> None:
        """Append the line."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as handle:
            handle.write(line_render(result))
