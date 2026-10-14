"""The shapes: construction, failure records, JSON round trip."""

from __future__ import annotations

import json

from hostlib.models import HostFacts, JobLogs, JobResult, JobSpec, JobStarted, ProgressEvent


def test_jobSpec_defaults() -> None:
    spec: JobSpec = JobSpec(["echo", "hi"])
    assert spec.cwd is None and spec.env is None and spec.stdin is None and spec.timeout is None
    assert spec.encoding == "utf-8"


def test_jobResult_failed_hasNoExitStatus() -> None:
    result: JobResult = JobResult.failed(["x", "y"], ["cannot run x"], startedAt="t", cwd="/w")
    assert result.status is False
    assert result.returncode is None and result.pid is None
    assert result.argv == ["x", "y"] and result.errors == ["cannot run x"]
    assert result.host.cwd == "/w" and result.startedAt == "t" and result.endedAt == "t"


def test_jobResult_toJson_roundTrips() -> None:
    facts: HostFacts = HostFacts("box", "ann", 7, "Linux", "/w", "2026-10-13T10:00:00+00:00")
    result: JobResult = JobResult(True, ["true"], 0, "", "", [], facts, "a", "b", 0.5, "/w", 99)
    data: dict = json.loads(result.toJson())
    assert data["status"] is True and data["host"]["hostname"] == "box" and data["pid"] == 99
    assert JobResult(**{**data, "host": HostFacts(**data["host"])}) == result


def test_jobStarted_toDict_carriesLogs() -> None:
    facts: HostFacts = HostFacts("box", "ann", 7, "Linux", "/w", "t")
    logs: JobLogs = JobLogs("/o/j-cmd", "/o/j-stdout", "/o/j-stderr", "/o/j-returncode")
    started: JobStarted = JobStarted(5, ["sleep"], "/w", "t", facts, logs)
    assert started.toDict()["logs"]["stdout"] == "/o/j-stdout"
    assert JobStarted(5, ["sleep"], "/w", "t", facts).toDict()["logs"] is None


def test_progressEvent_defaults() -> None:
    event: ProgressEvent = ProgressEvent("running", current=3, total=10)
    assert event.label == "" and event.percent is None and event.status == ""
