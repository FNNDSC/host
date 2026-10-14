"""What a sink receives besides the output streams.

Key components:
    - ProgressEvent: a structured progress report a job's runner can emit

Dependencies:
    - standard library only
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProgressEvent:
    """One step of progress, in a form a bar or a log can show.

    Attributes:
        phase: what is happening, ``"started"``, ``"running"``, ``"ended"`` or a
            program's own word.
        label: what the phase is about.
        current: how far along, in ``unit``s, when known.
        total: how far there is to go, when known.
        percent: ``current / total`` as a percentage, when known.
        unit: what ``current`` and ``total`` count.
        status: a word on how it is going, ``"ok"`` or ``"error"``.

    Example:
        >>> ProgressEvent("running", current=3, total=10).current
        3
    """

    phase: str
    label: str = ""
    current: int | None = None
    total: int | None = None
    percent: float | None = None
    unit: str = ""
    status: str = ""
