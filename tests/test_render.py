"""Captured output as a terminal would show it."""

from __future__ import annotations

from pathlib import Path

from hostlib import JobResult, terminal_render
from hostlib.models import HostFacts
from hostlib.proc.render import line_render
from hostlib.sink import FileSink


def test_line_render_lastFrameWins() -> None:
    assert line_render("10%\r20%\r100% done") == "100% done"
    assert line_render("plain") == "plain"
    assert line_render("") == ""


def test_line_render_shortRedrawLeavesTail() -> None:
    assert line_render("abcdef\rXY") == "XYcdef"
    assert line_render("abc\r") == "abc"


def test_terminal_render_keepsLines_andTrailingNewline() -> None:
    raw: str = " 50%|#####     |\r100%|##########|\nprocessed 100 items\n"
    assert terminal_render(raw) == "100%|##########|\nprocessed 100 items\n"
    assert terminal_render("no redraws\n") == "no redraws\n"
    assert terminal_render("") == ""


def test_terminal_render_tqdmShape() -> None:
    frames: str = "".join(f"\r{i:3d}%|{'#' * i}{' ' * (100 - i)}| {i}/100" for i in range(1, 101)) + "\n"
    rendered: str = terminal_render(frames)
    assert rendered == f"100%|{'#' * 100}| 100/100\n"
    assert frames.count("\r") == 100


def test_fileSink_rendered_rewritesStreamsAtEnd(tmp_path: Path) -> None:
    sink: FileSink = FileSink(tmp_path / "job", rendered=True)
    sink.began(["x"])
    sink.stderr_write(" 1%\r")
    sink.stderr_write(" 2%\r")
    assert (tmp_path / "job-stderr").read_bytes() == b" 1%\r 2%\r"
    facts: HostFacts = HostFacts("box", "ann", 7, "Linux", "/w", "t")
    result: JobResult = JobResult(
        True, ["x"], 0, "a\rb\n", " 1%\r 2%\r100%\n", [], facts, "s", "e", 0.1, "/w", 9
    )
    sink.ended(result)
    assert (tmp_path / "job-stderr").read_text() == "100%\n"
    assert (tmp_path / "job-stdout").read_text() == "b\n"
    raw: FileSink = FileSink(tmp_path / "raw")
    raw.began(["x"])
    raw.stderr_write(" 1%\r 2%\r100%\n")
    raw.ended(result)
    assert (tmp_path / "raw-stderr").read_bytes() == b" 1%\r 2%\r100%\n"
