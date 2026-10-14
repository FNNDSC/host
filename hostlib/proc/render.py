"""What a terminal would show of a process's output.

A program that draws a progress bar writes the same line many times, each attempt
preceded by a carriage return that moves the cursor back to the start of the line. On a
terminal the eye sees only the last frame; in a captured record every frame is there,
which is the truth but not what anyone wants to read. ``terminal_render`` applies the
terminal's rule to the captured text: a carriage return returns to the start of the
current line and what follows overwrites what was there; a newline keeps the line and
starts the next. The record's text stays as written; this is a view of it.

Key components:
    - terminal_render: the view

Typical usage:
    print(terminal_render(result.stderr))

Dependencies:
    - standard library only
"""

from __future__ import annotations


def line_render(line: str) -> str:
    """One line, as a terminal would leave it after every carriage return in it.

    Args:
        line: text without newlines, possibly containing carriage returns.

    Returns:
        The characters visible at the end.

    Example:
        >>> line_render("10%\\r20%\\r100% done")
        '100% done'
        >>> line_render("abcdef\\rXY")
        'XYcdef'
    """
    if "\r" not in line:
        return line
    screen: list[str] = []
    cursor: int = 0
    for index, segment in enumerate(line.split("\r")):
        if index:
            cursor = 0
        for character in segment:
            if cursor < len(screen):
                screen[cursor] = character
            else:
                screen.append(character)
            cursor += 1
    return "".join(screen)


def terminal_render(text: str) -> str:
    """The text as a terminal would show it, each line reduced to its final frame.

    Args:
        text: captured output, possibly with carriage-return redraws.

    Returns:
        The same lines, each as it last appeared; a trailing newline is kept.

    Example:
        >>> terminal_render(" 50%|#####     |\\r100%|##########|\\nprocessed 100 items\\n")
        '100%|##########|\\nprocessed 100 items\\n'
    """
    if "\r" not in text:
        return text
    return "\n".join(line_render(line) for line in text.split("\n"))
