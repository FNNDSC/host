"""``python -m hostlib``: the ``hostlib`` command."""

from __future__ import annotations

import sys

from hostlib.cli.commands import main

if __name__ == "__main__":
    sys.exit(main())
