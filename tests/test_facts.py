"""What the host is."""

from __future__ import annotations

import os
import re
import socket

from hostlib.facts import facts, timestamp_now, user_name
from hostlib.models import HostFacts


def test_facts_describeThisProcess() -> None:
    here: HostFacts = facts()
    assert here.hostname == socket.gethostname()
    assert here.pid == os.getpid()
    assert here.cwd == os.getcwd()
    assert here.platform
    assert here.user == user_name()


def test_facts_takesCwd() -> None:
    assert facts("/elsewhere").cwd == "/elsewhere"


def test_timestamp_isIsoWithOffset() -> None:
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", timestamp_now())
