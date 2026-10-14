"""The demo: a batch through one sink, and the bar sink it draws with."""

from __future__ import annotations

import io
import time
from pathlib import Path

import pytest

from hostlib import JobResult, JobSpec, ProgressEvent, job_run
from hostlib.cli.commands import main
from hostlib.cli.demo import batch_run, jobs_demo, progress_spec
from hostlib.sink import BarSink, NullSink, SinkBase


def test_batch_oneSinkSeesProgressAndOutput() -> None:
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

    results: list[JobResult] = batch_run(jobs_demo(pause=0.01), Record())
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


def test_batch_logDir_oneRecordPerJob(tmp_path: Path) -> None:
    results: list[JobResult] = batch_run(jobs_demo(pause=0.01), NullSink(), logDir=tmp_path)
    assert len(results) == 4
    assert (tmp_path / "convert-returncode").read_text() == "2\n"
    assert (tmp_path / "convert-stderr").read_text() == "bad input\n"
    assert (tmp_path / "report-stdout").read_text() == "done\n"
    assert "downloading 100%" in (tmp_path / "download-stdout").read_text()


def test_barSink_drawsInPlace_countsFailures_endsLine() -> None:
    err: io.StringIO = io.StringIO()
    bar: BarSink = BarSink(err=err, width=10)
    bar.progress_write(ProgressEvent("started", current=0, total=4))
    bar.status_write("running x\n")
    bar.progress_write(ProgressEvent("running", current=2, total=4, status="error"))
    bar.progress_write(ProgressEvent("ended", current=4, total=4, status="ok"))
    drawn: str = err.getvalue()
    assert drawn.count("\r") == 4 and drawn.endswith("\n")
    assert "[..........] 0/4  " in drawn
    assert "[#####.....] 2/4  1 failed  running x" in drawn
    assert bar.render() == "[##########] 4/4  1 failed  running x"


def test_barSink_ignoresStreams() -> None:
    err: io.StringIO = io.StringIO()
    bar: BarSink = BarSink(err=err)
    bar.began(["x"])
    bar.stdout_write("noise")
    bar.stderr_write("noise")
    assert err.getvalue() == ""


def test_main_demo_streamMode(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--stream", "--no-log", "--pause", "0.01"]) == 1
    captured = capsys.readouterr()
    assert "line 2" in captured.out and "done" in captured.out
    assert captured.out.count("FAIL") == 1 and captured.out.count("ok  ") == 3
    assert "records in" not in captured.out
    assert "bad input" in captured.err


def test_main_demo_barMode_writesRecords(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--log", str(tmp_path / "d"), "--pause", "0.01"]) == 1
    captured = capsys.readouterr()
    assert "\r[" in captured.err and captured.err.rstrip().endswith("running report")
    assert f"records in {tmp_path / 'd'}/" in captured.out
    assert (tmp_path / "d" / "scan-stdout").read_text() == "line 0\nline 1\nline 2\n"


def test_progressSpec_streamsEachRedrawAsItHappens() -> None:
    arrivals: list[tuple[float, str]] = []

    class Clock(SinkBase):
        def stderr_write(self, text: str) -> None:
            arrivals.append((time.monotonic(), text))

    spec: JobSpec = progress_spec(steps=10, step=0.05)
    result: JobResult = job_run(spec, sink=Clock())
    assert result.status is True and result.stdout == "processed 10 items\n"
    joined: str = "".join(text for _, text in arrivals)
    assert joined == result.stderr
    assert joined.count("\r") == 10 and joined.endswith("\n")
    assert "100%|" in joined and "| 10/10 [" in joined and "it/s]" in joined
    assert len(arrivals) >= 8
    assert arrivals[-1][0] - arrivals[0][0] >= 0.3


def test_main_demo_progress(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--progress", "--steps", "5", "--step", "0.01", "--no-log"]) == 0
    captured = capsys.readouterr()
    assert captured.err.count("\r") == 5 and "100%|" in captured.err
    assert "record: status=True exit=0" in captured.out
    assert "5 redraws" in captured.out and "record: stdout 'processed 5 items\\n'" in captured.out
    assert "terminal_render(stderr): '100%|" in captured.out
