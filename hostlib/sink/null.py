"""The sink that discards everything: output is captured into the record and nowhere else."""

from __future__ import annotations

from hostlib.sink.protocol import SinkBase


class NullSink(SinkBase):
    """Receives everything, keeps nothing. The default sink."""
