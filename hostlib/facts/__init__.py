"""hostlib.facts: what the host is."""

from __future__ import annotations

from hostlib.facts.facts import facts, timestamp_now, user_name

__all__: list[str] = ["facts", "timestamp_now", "user_name"]
