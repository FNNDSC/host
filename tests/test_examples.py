"""The examples run, and show what they claim to show."""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from types import ModuleType

import pytest

from hostlib import JobResult, ProgressEvent
from hostlib.sink import SinkBase

EXAMPLES: Path = Path(__file__).resolve().parent.parent / "examples"


def example_load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_batch_oneSinkSeesProgressAndOutput() -> None:
    batch = example_load("batch")
    events: list[str] = []

    class Record(SinkBase):
        def status_write(self, text: str) -> None:
            events.append(f"status:{text}")

        def progress_write(self, event: ProgressEvent) -> None:
            events.append(f"progress:{event.phase}:{event.current}/{event.total}:{event.status}")

        def stdout_write(self, text: str) -> None:
            events.append(f"out:{text!r}")

        def ended(self, result: JobResult) -> None:
            events.append(f"ended:{result.returncode}")

    results = batch.batch_run(batch.jobs_demo(pause=0.01), Record())
    assert [r.status for r in results] == [True, True, False, True]
    assert events[0] == "progress:started:0/4:"
    assert events[-1] == "progress:ended:4/4:ok"
    assert "progress:running:3/4:error" in events
    assert [e for e in events if e.startswith("status:")] == [
        "status:running scan",
        "status:running download",
        "status:running convert",
        "status:running report",
    ]
    assert any("downloading 100%" in e for e in events if e.startswith("out:"))
    assert events.index("ended:0") < events.index("progress:running:1/4:ok")


def test_batch_barDrawsInPlace() -> None:
    batch = example_load("batch")
    err: io.StringIO = io.StringIO()
    bar = batch.BarSink(err=err, width=10)
    bar.progress_write(ProgressEvent("started", current=0, total=4))
    bar.status_write("running x")
    bar.progress_write(ProgressEvent("running", current=2, total=4, status="error"))
    bar.progress_write(ProgressEvent("ended", current=4, total=4, status="ok"))
    drawn: str = err.getvalue()
    assert drawn.count("\r") == 4 and drawn.endswith("\n")
    assert "[#####.....] 2/4  1 failed  running x" in drawn
    assert "[##########] 4/4  1 failed" in drawn


def test_batch_main_streamMode(capsys: pytest.CaptureFixture[str]) -> None:
    batch = example_load("batch")
    code: int = batch.main(["--stream", "--pause", "0.01"])
    assert code == 1
    captured = capsys.readouterr()
    assert "line 2" in captured.out and "done" in captured.out
    assert captured.out.count("FAIL") == 1 and captured.out.count("ok  ") == 3
    assert "bad input" in captured.err


def test_batch_logDir_oneRecordPerJob(tmp_path: Path) -> None:
    batch = example_load("batch")
    from hostlib.sink import NullSink

    results = batch.batch_run(batch.jobs_demo(pause=0.01), NullSink(), logDir=tmp_path)
    assert len(results) == 4
    assert (tmp_path / "convert-returncode").read_text() == "2\n"
    assert (tmp_path / "report-stdout").read_text() == "done\n"
    assert "downloading 100%" in (tmp_path / "download-stdout").read_text()
