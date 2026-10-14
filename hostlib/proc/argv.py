"""Command lines as text: split once, before anything is substituted.

Key components:
    - argv_fromTemplate: shell-style splitting of a command string, no shell
    - argv_join: the inverse, for showing a command

Typical usage:
    argv = argv_fromTemplate('convert "%{in}" "%{out}"')  # ['convert', '%{in}', '%{out}']

Dependencies:
    - standard library only
"""

from __future__ import annotations

import shlex


def argv_fromTemplate(template: str) -> list[str]:
    """Split a command written as text into an argument list, honouring quotes.

    The split happens once, before any substitution into the arguments, so a value
    substituted later cannot change how many arguments there are.

    Args:
        template: the command as a user would type it in a shell.

    Returns:
        The argument list; empty for blank text.

    Raises:
        ValueError: the text has an unclosed quote.

    Example:
        >>> argv_fromTemplate("cp 'a b' c")
        ['cp', 'a b', 'c']
    """
    try:
        return shlex.split(template, posix=True)
    except ValueError as err:
        raise ValueError(f"cannot split command {template!r}: {err}") from err


def argv_join(argv: list[str]) -> str:
    """An argument list as one shell-safe line, for showing what ran.

    Args:
        argv: the argument list.

    Returns:
        The quoted command line.

    Example:
        >>> argv_join(["cp", "a b", "c"])
        "cp 'a b' c"
    """
    return shlex.join(argv)
