"""The ``hostlib`` command."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from hostlib import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command.

    Args:
        argv: arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        0.
    """
    args: list[str] = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("--version", "-V"):
        print(f"hostlib {__version__}")
        return 0
    print(f"hostlib {__version__}: run a program, stream its output, keep the record")
    return 0


if __name__ == "__main__":
    sys.exit(main())
