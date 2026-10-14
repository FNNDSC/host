"""The hostlib command."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from hostlib import __version__
from hostlib.cli.commands import main, manual_build, parser_build
from hostlib.cli.manual import (
    BG_PAGE,
    FG_BANNER,
    FG_BODY,
    FG_COMMAND,
    FG_FLAG,
    FG_HEADING,
    FG_PLACEHOLDER,
    FG_STRING,
    FG_VERSION,
    NO_COLOUR,
    banner_render,
    cliLine_highlight,
    inlineCode_render,
    synopsis_colourize,
)

PYTHON: str = sys.executable


def test_main_run_passesThroughExitStatus_andStreams(capsys: pytest.CaptureFixture[str]) -> None:
    code: int = main(
        [
            "run",
            "--",
            PYTHON,
            "-c",
            "import sys; print('o'); print('e', file=sys.stderr); raise SystemExit(5)",
        ]
    )
    assert code == 5
    captured = capsys.readouterr()
    assert captured.out == "o\n" and captured.err == "e\n"


def test_main_run_jsonQuiet_printsOnlyRecord(capsys: pytest.CaptureFixture[str]) -> None:
    code: int = main(["run", "--json", "--quiet", "--", PYTHON, "-c", "print('hidden')"])
    assert code == 0
    record: dict = json.loads(capsys.readouterr().out)
    assert record["status"] is True and record["stdout"] == "hidden\n" and record["host"]["pid"]


def test_main_run_missingProgramIs127(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--", "no_such_program_hostlib"]) == 127
    assert "cannot run no_such_program_hostlib" in capsys.readouterr().err


def test_main_run_timeoutIs124(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["run", "--timeout", "0.2", "--quiet", "--", PYTHON, "-c", "import time; time.sleep(10)"]) == 124
    )
    assert "timed out after 0.2s" in capsys.readouterr().err


def test_main_run_logWritesFiles_envAndCwdApply(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code: int = main(
        [
            "run",
            "--quiet",
            "--log",
            str(tmp_path / "out" / "job"),
            "--cwd",
            str(tmp_path),
            "--env",
            "HOSTLIB_CLI=yes",
            "--",
            PYTHON,
            "-c",
            "import os; print(os.environ['HOSTLIB_CLI'], os.getcwd())",
        ]
    )
    assert code == 0
    assert (tmp_path / "out" / "job-stdout").read_text() == f"yes {tmp_path.resolve()}\n"
    assert (tmp_path / "out" / "job-returncode").read_text() == "0\n"


def test_main_run_stdin(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["run", "--stdin", "abc", "--", PYTHON, "-c", "import sys; print(sys.stdin.read()[::-1])"]) == 0
    )
    assert capsys.readouterr().out == "cba\n"


def test_main_run_nothingToRunIsUsageError() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["run", "--"])
    assert exc.value.code == 2


def test_main_run_badEnvIsUsageError() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["run", "--env", "NOEQUALS", "--", "true"])
    assert exc.value.code == 2


def test_main_facts_printsJson(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["facts", "--json"]) == 0
    record: dict = json.loads(capsys.readouterr().out)
    assert set(record) == {"hostname", "user", "pid", "platform", "cwd", "timestamp"}


def test_main_facts_printsTable(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["facts"]) == 0
    assert capsys.readouterr().out.startswith("hostname ")


def test_main_noCommandPrintsHelp_exitsTwo(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "hostlib --man" in capsys.readouterr().out


def test_main_versionExitsZero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"hostlib {__version__}"


def test_main_manPrintsFullManual(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--man"]) == 0
    text: str = capsys.readouterr().out
    for heading in ("NAME", "SYNOPSIS", "DESCRIPTION", "ARGS", "THE RECORD", "EXIT STATUS", "EXAMPLES"):
        assert re.search(rf"^    {heading}\s*$", text, re.M), heading
    assert "``" not in text
    assert f"version {__version__}" in text
    assert "--timeout <seconds>" in text


def test_main_synopsisPrintsBriefManual(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--synopsis"]) == 0
    text: str = capsys.readouterr().out
    assert "SYNOPSIS" in text and "BRIEF EXAMPLE" in text and "DESCRIPTION" not in text


def test_parser_build_runTakesRemainder() -> None:
    args = parser_build().parse_args(["run", "--timeout", "2", "--", "ls", "-l", "--not-ours"])
    assert args.argv == ["--", "ls", "-l", "--not-ours"] and args.timeout == 2.0


def test_cliLine_highlight_coloursEachTokenKind() -> None:
    manual = manual_build()
    line: str = "        hostlib run --timeout <seconds> 'x y' \\"
    coloured: str = cliLine_highlight(line, manual.cliToken_pattern())
    assert FG_COMMAND + "hostlib" + FG_BODY in coloured
    assert FG_FLAG + "--timeout" + FG_BODY in coloured
    assert FG_PLACEHOLDER + "<seconds>" + FG_BODY in coloured
    assert FG_STRING + "'x y'" + FG_BODY in coloured
    assert coloured.endswith("\\" + FG_BODY)


def test_banner_render_coloursArtTitleProseAndVersion() -> None:
    manual = manual_build()
    page: str = banner_render(manual, colour=True, width=80)
    assert BG_PAGE + FG_BANNER in page
    assert BG_PAGE + FG_HEADING + "                            " + manual.title in page
    assert FG_VERSION + __version__ + FG_BODY in page
    plain: str = banner_render(manual, colour=False)
    assert plain.startswith(manual.art) and "``" not in plain and "hostlib is a library first" in plain


def test_inlineCode_render_dropsBackticksAndColours() -> None:
    assert inlineCode_render("use ``hostlib run`` now", colour=False) == "use hostlib run now"
    assert inlineCode_render("use ``x``", colour=True) == "use " + FG_FLAG + "x" + FG_BODY


def test_synopsis_colourize_padsEveryLineToWidth() -> None:
    manual = manual_build()
    page: str = synopsis_colourize(manual, manual.synopsisFull, width=120)
    escape: re.Pattern[str] = re.compile(r"\033\[[0-9;]*m")
    for line in page.splitlines():
        assert line.startswith(BG_PAGE) and line.endswith(NO_COLOUR)
        assert len(escape.sub("", line)) == 120, line
    assert BG_PAGE + FG_HEADING + "    EXAMPLES" in page


def test_main_run_jsonlAppendsRecord(tmp_path: Path) -> None:
    path: Path = tmp_path / "records" / "jobs.jsonl"
    for _ in range(2):
        assert main(["run", "--quiet", "--jsonl", str(path), "--", PYTHON, "-c", "print('hi')"]) == 0
    lines: list[str] = path.read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["stdout"] == "hi\n"
