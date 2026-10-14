"""Running a job in the foreground: every way a run can go."""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path
from typing import Any

from hostlib import JobResult, JobSpec, job_run
from hostlib.sink import ConsoleSink, FileSink, SinkBase, TeeSink

PYTHON: str = sys.executable


def python_spec(code: str, **kwargs: Any) -> JobSpec:
    return JobSpec([PYTHON, "-c", code], **kwargs)


def test_run_success_capturesBothStreams() -> None:
    result: JobResult = job_run(python_spec("import sys; print('out'); print('err', file=sys.stderr)"))
    assert result.status is True and result.returncode == 0
    assert result.stdout == "out\n" and result.stderr == "err\n"
    assert result.errors == [] and result.timedOut is False
    assert result.pid and result.pid > 0
    assert result.host.pid == os.getpid()
    assert result.duration >= 0 and result.startedAt <= result.endedAt


def test_run_nonZeroExit_isFailedWithReason() -> None:
    result: JobResult = job_run(python_spec("raise SystemExit(3)"))
    assert result.status is False and result.returncode == 3
    assert result.errors == ["exit status 3"]


def test_run_missingProgram_isFailedNeverRan() -> None:
    result: JobResult = job_run(JobSpec(["no_such_program_hostlib"]))
    assert result.status is False and result.returncode is None and result.pid is None
    assert result.errors == ["cannot run no_such_program_hostlib: No such file or directory"]
    assert result.argv == ["no_such_program_hostlib"]


def test_run_emptyArgv_isFailed() -> None:
    result: JobResult = job_run(JobSpec([]))
    assert result.status is False and result.errors == ["argv is empty"]


def test_run_argumentWithSpaceStaysOneArgument() -> None:
    result: JobResult = job_run(
        JobSpec([PYTHON, "-c", "import sys; print(len(sys.argv[1:]), sys.argv[1])", "a b; rm x"])
    )
    assert result.stdout == "1 a b; rm x\n"


def test_run_lastLineWithoutNewlineIsKept() -> None:
    result: JobResult = job_run(python_spec("import sys; sys.stdout.write('one\\ntwo'); sys.stdout.flush()"))
    assert result.stdout == "one\ntwo"


def test_run_largeStderrDoesNotDeadlock() -> None:
    code: str = "import sys; sys.stderr.write('e' * 2_000_000); sys.stdout.write('o' * 2_000_000)"
    started: float = time.monotonic()
    result: JobResult = job_run(python_spec(code))
    assert result.status is True
    assert len(result.stdout) == 2_000_000 and len(result.stderr) == 2_000_000
    assert time.monotonic() - started < 30


def test_run_utf8SplitAcrossReadsDecodesWhole() -> None:
    code: str = (
        "import sys, time\n"
        "b = ('é' * 40000).encode()\n"
        "sys.stdout.buffer.write(b[:1]); sys.stdout.buffer.flush(); time.sleep(0.05)\n"
        "sys.stdout.buffer.write(b[1:]); sys.stdout.buffer.flush()\n"
    )
    result: JobResult = job_run(python_spec(code))
    assert result.stdout == "é" * 40000


def test_run_stdinIsFedThenClosed() -> None:
    result: JobResult = job_run(
        python_spec("import sys; print(sys.stdin.read().upper(), end='')", stdin="abc")
    )
    assert result.stdout == "ABC"
    noStdin: JobResult = job_run(python_spec("import sys; print(repr(sys.stdin.read()))"))
    assert noStdin.stdout == "''\n"


def test_run_cwdAndEnvApply(tmp_path: Path) -> None:
    result: JobResult = job_run(
        python_spec(
            "import os; print(os.getcwd()); print(os.environ['HOSTLIB_T'])",
            cwd=str(tmp_path),
            env={"HOSTLIB_T": "v"},
        )
    )
    assert result.stdout.splitlines() == [str(tmp_path.resolve()), "v"]
    assert result.cwd == str(tmp_path.resolve()) and result.host.cwd == result.cwd
    assert (
        "PATH" in os.environ
        and job_run(python_spec("import os; print('PATH' in os.environ)")).stdout == "True\n"
    )


def test_run_badCwdIsFailedNeverRan(tmp_path: Path) -> None:
    result: JobResult = job_run(JobSpec(["true"], cwd=str(tmp_path / "missing")))
    assert result.status is False and result.returncode is None
    assert result.errors[0].startswith("cannot run true:")


def test_run_timeoutTerminates() -> None:
    started: float = time.monotonic()
    result: JobResult = job_run(
        python_spec("import time; print('go', flush=True); time.sleep(30)", timeout=0.3)
    )
    assert time.monotonic() - started < 10
    assert result.status is False and result.timedOut is True
    assert result.returncode is not None and result.returncode != 0
    assert result.errors == ["timed out after 0.3s"]
    assert result.stdout == "go\n"


def test_run_streamsToSinkWhileRunning() -> None:
    arrivals: list[tuple[float, str]] = []

    class Clock(SinkBase):
        def stdout_write(self, text: str) -> None:
            arrivals.append((time.monotonic(), text))

    code: str = "import time; print('first', flush=True); time.sleep(0.4); print('second', flush=True)"
    result: JobResult = job_run(python_spec(code), sink=Clock())
    assert result.stdout == "first\nsecond\n"
    assert len(arrivals) == 2
    assert arrivals[1][0] - arrivals[0][0] >= 0.3


def test_run_sinkSeesBeganAndEnded_andCarriageReturnProgress() -> None:
    seen: list[str] = []

    class Watch(SinkBase):
        def began(self, argv: list[str]) -> None:
            seen.append(f"began:{argv[0] == PYTHON}")

        def stdout_write(self, text: str) -> None:
            seen.append(f"out:{text!r}")

        def ended(self, result: JobResult) -> None:
            seen.append(f"ended:{result.returncode}")

    code: str = "import sys; sys.stdout.write('10%\\r'); sys.stdout.flush(); sys.stdout.write('100%\\n')"
    job_run(python_spec(code), sink=Watch())
    assert seen[0] == "began:True" and seen[-1] == "ended:0"
    assert "".join(s[4:] for s in seen[1:-1] if s.startswith("out:")).replace("'", "") == "10%\\r100%\\n"


def test_run_consoleAndFileTee(tmp_path: Path) -> None:
    out: io.StringIO = io.StringIO()
    err: io.StringIO = io.StringIO()
    sink: TeeSink = TeeSink(ConsoleSink(out=out, err=err), FileSink(tmp_path / "job"))
    result: JobResult = job_run(
        python_spec("import sys; print('o'); print('e', file=sys.stderr); raise SystemExit(2)"), sink=sink
    )
    assert out.getvalue() == "o\n" and err.getvalue() == "e\n"
    assert (tmp_path / "job-stdout").read_text() == "o\n"
    assert (tmp_path / "job-stderr").read_text() == "e\n"
    assert (tmp_path / "job-returncode").read_text() == "2\n"
    assert (tmp_path / "job-cmd").read_text().startswith(PYTHON if " " not in PYTHON else "'")
    assert result.returncode == 2
