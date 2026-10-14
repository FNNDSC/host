"""The package imports and names its version."""

from __future__ import annotations

import re

from host import __version__
from host.cli.__main__ import main


def test_version_isSemver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_cli_printsVersion(capsys) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"host {__version__}"
