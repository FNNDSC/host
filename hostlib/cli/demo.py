"""``hostlib demo``: a batch of jobs through one sink, to see the library work.

The caller owns the batch, so the caller emits the progress: a status line before each
job and a progress event after it. The jobs' own output flows through the same sink as
it arrives. Which of that reaches the terminal, which reaches files, is decided once,
where the sink is built, and the batch loop never knows.

    hostlib demo            # a bar on stderr, each job's record under ./hostlib-demo
    hostlib demo --stream   # no bar; every line of every job as it happens
    hostlib demo --both     # the bar, and the lines scrolling under it

Key components:
    - batch_run: the loop; the only place that knows there is a batch
    - jobs_demo: four small jobs, one of which draws its own progress with carriage returns
    - demo_command: the subcommand

Dependencies:
    - hostlib.proc, hostlib.sink, hostlib.models
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hostlib.models.proc import JobResult, JobSpec
from hostlib.models.sink import ProgressEvent
from hostlib.proc.run import job_run
from hostlib.sink.bar import BarSink
from hostlib.sink.console import ConsoleSink
from hostlib.sink.file import FileSink
from hostlib.sink.null import NullSink
from hostlib.sink.protocol import JobSink
from hostlib.sink.tee import TeeSink

DEFAULT_LOG_DIR: Path = Path("hostlib-demo")


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


def demoParser_add(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the ``demo`` subcommand to the command's parser."""
    demo: argparse.ArgumentParser = commands.add_parser("demo", help="run a small batch through one sink")
    demo.add_argument("--stream", action="store_true", help="stream every job's output; no bar")
    demo.add_argument("--both", action="store_true", help="the bar and the streamed output")
    demo.add_argument("--log", type=Path, default=None, help="directory for per-job records")
    demo.add_argument("--no-log", action="store_true", help="write no per-job records")
    demo.add_argument("--pause", type=float, default=0.3, help="seconds between a job's lines")


def demo_command(args: argparse.Namespace) -> int:
    """``hostlib demo``."""
    bar: bool = args.both or not args.stream
    stream: bool = args.stream or args.both
    logDir: Path | None = None if args.no_log else (args.log if args.log is not None else DEFAULT_LOG_DIR)
    jobs: dict[str, JobSpec] = jobs_demo(args.pause)
    results: list[JobResult] = batch_run(jobs, sink_build(stream, bar), logDir)
    for name, result in zip(jobs, results, strict=True):
        mark: str = "ok  " if result.status else "FAIL"
        print(f"{mark} {name:10} exit={result.returncode} {result.duration:.2f}s {'; '.join(result.errors)}")
    if logDir is not None:
        print(f"records in {logDir}/")
    return 0 if all(result.status for result in results) else 1
