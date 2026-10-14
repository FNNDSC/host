"""Command lines as text."""

from __future__ import annotations

import pytest

from hostlib.proc import argv_fromTemplate, argv_join


def test_argv_fromTemplate_honoursQuotes() -> None:
    assert argv_fromTemplate("""cp 'a b' "c d" e""") == ["cp", "a b", "c d", "e"]


def test_argv_fromTemplate_keepsTagsIntact() -> None:
    assert argv_fromTemplate('convert "%{in}" %{out|rmext}.png') == ["convert", "%{in}", "%{out|rmext}.png"]


def test_argv_fromTemplate_blankIsEmpty() -> None:
    assert argv_fromTemplate("   ") == []


def test_argv_fromTemplate_unclosedQuoteRaises() -> None:
    with pytest.raises(ValueError, match="cannot split command"):
        argv_fromTemplate("echo 'oops")


def test_argv_join_quotesWhatNeedsIt() -> None:
    assert argv_join(["cp", "a b", "c"]) == "cp 'a b' c"
    assert argv_fromTemplate(argv_join(["x", "it's", "$HOME"])) == ["x", "it's", "$HOME"]
