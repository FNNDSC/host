"""Where output goes while a job runs."""

from __future__ import annotations

import io
from pathlib import Path

from hostlib.models import HostFacts, JobResult, ProgressEvent
from hostlib.sink import LOG_SUFFIXES, ConsoleSink, FileSink, JobSink, NullSink, SinkBase, TeeSink


def result_make(returncode: int = 0) -> JobResult:
    facts: HostFacts = HostFacts("box", "ann", 7, "Linux", "/w", "t")
    return JobResult(returncode == 0, ["x"], returncode, "", "", [], facts, "a", "b", 0.1, "/w", 9)


def test_sinkBase_satisfiesProtocol_andDoesNothing() -> None:
    sink: SinkBase = SinkBase()
    assert isinstance(sink, JobSink) and isinstance(NullSink(), JobSink)
    sink.began(["x"])
    sink.stdout_write("a")
    sink.stderr_write("b")
    sink.status_write("c")
    sink.progress_write(ProgressEvent("running"))
    sink.ended(result_make())


def test_consoleSink_keepsStreamsApart_andFlushes() -> None:
    out: io.StringIO = io.StringIO()
    err: io.StringIO = io.StringIO()
    sink: ConsoleSink = ConsoleSink(out=out, err=err)
    sink.stdout_write("o1")
    sink.stderr_write("e1")
    sink.stdout_write("o2\n")
    sink.status_write("busy")
    assert out.getvalue() == "o1o2\n"
    assert err.getvalue() == "e1busy\n"


def test_consoleSink_progressAsOneLine() -> None:
    err: io.StringIO = io.StringIO()
    ConsoleSink(out=io.StringIO(), err=err).progress_write(
        ProgressEvent("running", label="slices", current=3, total=10, unit="files", status="ok")
    )
    assert err.getvalue() == "running slices 3/10 files [ok]\n"
    quiet: io.StringIO = io.StringIO()
    ConsoleSink(out=io.StringIO(), err=quiet, progress=False).progress_write(ProgressEvent("x"))
    assert quiet.getvalue() == ""


def test_fileSink_writesFourFiles_liveAndInOrder(tmp_path: Path) -> None:
    prefix: Path = tmp_path / "out" / "job"
    sink: FileSink = FileSink(prefix)
    assert sink.logs.cmd == str(tmp_path / "out" / "job-cmd")
    sink.began(["cp", "a b", "c"])
    assert (tmp_path / "out" / "job-cmd").read_text() == "cp 'a b' c\n"
    sink.stdout_write("partial")
    assert (tmp_path / "out" / "job-stdout").read_text() == "partial"
    sink.stderr_write("warn\n")
    sink.stdout_write(" more\n")
    sink.ended(result_make(3))
    assert (tmp_path / "out" / "job-stdout").read_text() == "partial more\n"
    assert (tmp_path / "out" / "job-stderr").read_text() == "warn\n"
    assert (tmp_path / "out" / "job-returncode").read_text() == "3\n"
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(f"job-{s}" for s in LOG_SUFFIXES)


def test_fileSink_writesNothingBeforeBegan(tmp_path: Path) -> None:
    sink: FileSink = FileSink(tmp_path / "job")
    sink.stdout_write("lost")
    assert not (tmp_path / "job-stdout").exists()


def test_teeSink_forwardsEverything_inOrder() -> None:
    calls: list[str] = []

    class Recorder(SinkBase):
        def __init__(self, name: str) -> None:
            self.name: str = name

        def began(self, argv: list[str]) -> None:
            calls.append(f"{self.name}.began")

        def stdout_write(self, text: str) -> None:
            calls.append(f"{self.name}.out:{text}")

        def stderr_write(self, text: str) -> None:
            calls.append(f"{self.name}.err:{text}")

        def status_write(self, text: str) -> None:
            calls.append(f"{self.name}.status:{text}")

        def progress_write(self, event: ProgressEvent) -> None:
            calls.append(f"{self.name}.progress:{event.phase}")

        def ended(self, result: JobResult) -> None:
            calls.append(f"{self.name}.ended:{result.returncode}")

    tee: TeeSink = TeeSink(Recorder("a"), Recorder("b"))
    tee.began(["x"])
    tee.stdout_write("o")
    tee.stderr_write("e")
    tee.status_write("s")
    tee.progress_write(ProgressEvent("p"))
    tee.ended(result_make(2))
    assert calls == [
        "a.began",
        "b.began",
        "a.out:o",
        "b.out:o",
        "a.err:e",
        "b.err:e",
        "a.status:s",
        "b.status:s",
        "a.progress:p",
        "b.progress:p",
        "a.ended:2",
        "b.ended:2",
    ]
