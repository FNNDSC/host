"""hostlib.sink: where output goes while a job runs.

Key components:
    - JobSink, SinkBase: the protocol and a no-op base to subclass
    - NullSink, ConsoleSink, FileSink, JsonSink, TeeSink, BarSink: the shipped sinks
"""

from __future__ import annotations

from hostlib.sink.bar import BarSink
from hostlib.sink.console import ConsoleSink
from hostlib.sink.file import LOG_SUFFIXES, FileSink
from hostlib.sink.jsonl import JOBS_FILE, JsonSink
from hostlib.sink.null import NullSink
from hostlib.sink.protocol import JobSink, SinkBase
from hostlib.sink.tee import TeeSink

__all__: list[str] = [
    "JOBS_FILE",
    "LOG_SUFFIXES",
    "BarSink",
    "ConsoleSink",
    "FileSink",
    "JobSink",
    "JsonSink",
    "NullSink",
    "SinkBase",
    "TeeSink",
]
