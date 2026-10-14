"""Background jobs: start, poll, wait, terminate, record."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest

from hostlib import JobHandle, JobResult, JobSpec, JobStarted, job_start
from hostlib.sink import FileSink, NullSink, TeeSink

PYTHON: str = sys.executable


def python_spec(code: str, **kwargs: Any) -> JobSpec:
    return JobSpec([PYTHON, "-c", code], **kwargs)


def test_start_returnsAtOnce_thenPollAndWait() -> None:
    started: float = time.monotonic()
    handle: JobHandle = job_start(python_spec("import time; time.sleep(0.4); print('done')"))
    assert time.monotonic() - started < 0.3
    assert handle.pid > 0
    assert handle.poll() is None and handle.result() is None
    assert handle.wait(timeout=0.05) is None
    result: JobResult | None = handle.wait()
    assert result is not None and result.status is True and result.stdout == "done\n"
    assert handle.poll() == 0
    assert handle.result() is result


def test_start_resultBuiltOnce_sinkEndedOnce() -> None:
    endedCount: list[int] = []

    class Count(NullSink):
        def ended(self, result: JobResult) -> None:
            endedCount.append(result.returncode or 0)

    handle: JobHandle = job_start(python_spec("print('x')"), sink=Count())
    first: JobResult | None = handle.wait()
    second: JobResult | None = handle.result()
    third: JobResult | None = handle.wait()
    assert first is second is third
    assert endedCount == [0]


def test_start_terminate_recordsTimedOut() -> None:
    handle: JobHandle = job_start(python_spec("import time; print('up', flush=True); time.sleep(30)"))
    time.sleep(0.3)
    result: JobResult = handle.terminate(grace=1.0)
    assert result.timedOut is True and result.status is False
    assert result.errors == ["terminated"]
    assert result.stdout == "up\n"
    assert handle.poll() is not None


def test_start_terminate_killsAfterGrace() -> None:
    code: str = (
        "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ignoring', flush=True)\n"
        "while True: time.sleep(0.1)"
    )
    handle: JobHandle = job_start(python_spec(code))
    time.sleep(0.4)
    started: float = time.monotonic()
    result: JobResult = handle.terminate(grace=0.3)
    assert time.monotonic() - started < 5
    assert result.returncode == -9 and result.timedOut is True


def test_start_terminate_afterExitIsNotTimedOut() -> None:
    handle: JobHandle = job_start(python_spec("print('quick')"))
    handle.process.wait()
    result: JobResult = handle.terminate()
    assert result.timedOut is False and result.status is True and result.stdout == "quick\n"


def test_start_fileSinkWritesWhileRunning(tmp_path: Path) -> None:
    sink: FileSink = FileSink(tmp_path / "bg")
    handle: JobHandle = job_start(
        python_spec("import time; print('early', flush=True); time.sleep(0.6)"), sink=sink
    )
    time.sleep(0.3)
    assert (tmp_path / "bg-stdout").read_text() == "early\n"
    assert not (tmp_path / "bg-returncode").exists()
    handle.wait()
    assert (tmp_path / "bg-returncode").read_text() == "0\n"


def test_start_toRecord_namesLogs(tmp_path: Path) -> None:
    sink: TeeSink = TeeSink(NullSink(), FileSink(tmp_path / "x"))
    handle: JobHandle = job_start(python_spec("pass"), sink=sink)
    record: JobStarted = handle.toRecord()
    assert record.pid == handle.pid and record.argv[0] == PYTHON
    assert record.logs is not None and record.logs.cmd == str(tmp_path / "x-cmd")
    assert record.host.hostname and record.startedAt
    assert job_start(python_spec("pass")).toRecord().logs is None
    handle.wait()


def test_start_emptyArgvRaises() -> None:
    with pytest.raises(ValueError, match="argv is empty"):
        job_start(JobSpec([]))


def test_start_missingProgramRaisesOSError() -> None:
    with pytest.raises(OSError):
        job_start(JobSpec(["no_such_program_hostlib"]))
