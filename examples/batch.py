"""A batch of jobs through one sink: batch progress as a bar, job output as it streams.

The caller owns the batch, so the caller emits the progress: a status line before each
job and a progress event after it. The jobs' own output flows through the same sink as
it arrives. Which of that reaches the terminal, which reaches files, is decided once,
where the sink is built, and the batch code never knows.

    python examples/batch.py            # a bar on stderr, job output to ./batch-logs
    python examples/batch.py --stream   # no bar; every line of every job as it happens
    python examples/batch.py --both     # the bar, and the lines scrolling under it

Key components:
    - BarSink: draws progress_write as a bar and status_write as its label; ignores streams
    - batch_run: the loop; the only place that knows there is a batch
    - jobs_demo: four small jobs, one of which draws its own progress with carriage returns
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from hostlib import JobResult, JobSpec, ProgressEvent, job_run
from hostlib.sink import ConsoleSink, FileSink, JobSink, NullSink, SinkBase, TeeSink

BAR_WIDTH: int = 30


class BarSink(SinkBase):
    """A progress bar on one terminal line, redrawn on every status or progress event.

    Attributes:
        err: where the bar is drawn.
        width: the bar's width in characters.
        label: the current status line, drawn after the bar.
        current, total: the last progress seen.
    """

    def __init__(self, err: TextIO | None = None, width: int = BAR_WIDTH) -> None:
        self.err: TextIO = err if err is not None else sys.stderr
        self.width: int = width
        self.label: str = ""
        self.current: int = 0
        self.total: int = 0
        self.failed: int = 0

    def status_write(self, text: str) -> None:
        """A new label; redraw."""
        self.label = text
        self.draw()

    def progress_write(self, event: ProgressEvent) -> None:
        """Advance the bar; a final event ends the line."""
        if event.current is not None:
            self.current = event.current
        if event.total is not None:
            self.total = event.total
        if event.status == "error":
            self.failed += 1
        self.draw()
        if event.phase == "ended":
            self.err.write("\n")
            self.err.flush()

    def draw(self) -> None:
        """Redraw the bar in place."""
        filled: int = round(self.width * self.current / self.total) if self.total else 0
        bar: str = "#" * filled + "." * (self.width - filled)
        failed: str = f"  {self.failed} failed" if self.failed else ""
        line: str = f"[{bar}] {self.current}/{self.total}{failed}  {self.label}"
        self.err.write("\r" + line.ljust(self.width + 60))
        self.err.flush()


def batch_run(jobs: dict[str, JobSpec], sink: JobSink, logDir: Path | None = None) -> list[JobResult]:
    """Run the jobs in order, reporting the batch's progress through the same sink.

    Args:
        jobs: what to run, by name.
        sink: where everything goes: the batch's status and progress, and each job's output.
        logDir: when given, each job's record is also written there as ``<name>-cmd``,
            ``<name>-stdout``, ``<name>-stderr`` and ``<name>-returncode``.

    Returns:
        One record per job, in order.
    """
    results: list[JobResult] = []
    total: int = len(jobs)
    sink.progress_write(ProgressEvent("started", current=0, total=total, unit="jobs"))
    for index, (name, spec) in enumerate(jobs.items(), start=1):
        sink.status_write(f"running {name}")
        jobSink: JobSink = sink if logDir is None else TeeSink(sink, FileSink(logDir / name))
        result: JobResult = job_run(spec, sink=jobSink)
        results.append(result)
        sink.progress_write(
            ProgressEvent(
                "running" if index < total else "ended",
                label=name,
                current=index,
                total=total,
                unit="jobs",
                status="ok" if result.status else "error",
            )
        )
    return results


def jobs_demo(pause: float = 0.3) -> dict[str, JobSpec]:
    """Four jobs that take a moment and say something while they do.

    Args:
        pause: seconds each job spends between lines; small for tests.

    Returns:
        The specs by name. ``download`` draws its own carriage-return progress bar;
        ``convert`` exits non-zero.
    """
    python: str = sys.executable
    lines: str = f"import time\nfor i in range(3):\n    print('line', i, flush=True); time.sleep({pause})"
    ownBar: str = (
        "import sys, time\n"
        "for pct in range(0, 101, 20):\n"
        "    sys.stdout.write(f'\\r  downloading {pct:3d}%'); sys.stdout.flush()\n"
        f"    time.sleep({pause / 2})\n"
        "print()"
    )
    failing: str = (
        f"import sys, time; time.sleep({pause}); print('bad input', file=sys.stderr); raise SystemExit(2)"
    )
    quick: str = "print('done')"
    return {
        "scan": JobSpec([python, "-c", lines]),
        "download": JobSpec([python, "-c", ownBar]),
        "convert": JobSpec([python, "-c", failing]),
        "report": JobSpec([python, "-c", quick]),
    }


def sink_build(stream: bool, bar: bool) -> JobSink:
    """The sink the flags ask for: bar, stream, or both."""
    sinks: list[JobSink] = []
    if bar:
        sinks.append(BarSink())
    if stream:
        sinks.append(ConsoleSink(progress=not bar))
    if not sinks:
        return NullSink()
    return sinks[0] if len(sinks) == 1 else TeeSink(*sinks)


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--stream", action="store_true", help="stream every job's output; no bar")
    parser.add_argument("--both", action="store_true", help="the bar and the streamed output")
    parser.add_argument("--log", type=Path, default=None, help="directory for per-job log files")
    parser.add_argument("--pause", type=float, default=0.3, help="seconds between a job's lines")
    args: argparse.Namespace = parser.parse_args(argv)
    bar: bool = args.both or not args.stream
    stream: bool = args.stream or args.both
    logDir: Path | None = args.log if args.log is not None else (Path("batch-logs") if not stream else None)
    jobs: dict[str, JobSpec] = jobs_demo(args.pause)
    results: list[JobResult] = batch_run(jobs, sink_build(stream, bar), logDir)
    for name, result in zip(jobs, results, strict=True):
        mark: str = "ok  " if result.status else "FAIL"
        print(f"{mark} {name:10} exit={result.returncode} {result.duration:.2f}s {'; '.join(result.errors)}")
    if logDir is not None:
        print(f"logs in {logDir}/")
    return 0 if all(result.status for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
