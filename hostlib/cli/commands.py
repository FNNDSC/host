"""The ``hostlib`` command: ``run`` a program through the library, print the host's ``facts``.

``--help`` is argparse's quick reference; ``--man`` prints the full manual, ``--synopsis``
its first page.

Key components:
    - BANNER_*, SYNOPSIS_*, DESCRIPTION, ARGS, SINKS_HELP, EXAMPLES: the manual's text
    - synopsis, manual_build: the manual
    - parser_build: the parser, with ``run`` and ``facts`` subcommands
    - run_command, facts_command: the subcommands
    - main: the entry point, honouring an explicit ``argv``

Typical usage:
    hostlib run -- ls -l /tmp
    hostlib run --log /out/job --json -- mri_convert in.dcm out.nii.gz
    hostlib facts --json

Dependencies:
    - hostlib.proc, hostlib.sink, hostlib.facts, hostlib.cli.manual
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence

from hostlib import __version__
from hostlib.cli.demo import demo_command, demoParser_add
from hostlib.cli.manual import Manual, manual_print
from hostlib.facts.facts import facts
from hostlib.models.facts import HostFacts
from hostlib.models.proc import JobResult, JobSpec
from hostlib.proc.run import job_run
from hostlib.sink.console import ConsoleSink
from hostlib.sink.file import FileSink
from hostlib.sink.jsonl import JsonSink
from hostlib.sink.null import NullSink
from hostlib.sink.protocol import JobSink
from hostlib.sink.tee import TeeSink

EXIT_CANNOT_RUN: int = 127
EXIT_TIMED_OUT: int = 124
EXIT_USAGE: int = 2

BANNER_TITLE: str = "hostlib: run, stream, record"

BANNER_ART: str = r"""

  _               _   _ _ _
 | |__   ___  ___| |_| (_) |__
 | '_ \ / _ \/ __| __| | | '_ \
 | | | | (_) \__ \ |_| | | |_) |
 |_| |_|\___/|___/\__|_|_|_.__/

"""

BANNER_TEXT: str = """
                            hostlib: run, stream, record

        Run a program, see its output as it happens, and get back a record
        you can trust: the command as run, both output streams complete, the
        exit status, and the facts of the host it ran on.

                             -- version {version} --

        ``hostlib`` is a library first; this command runs a program through it
        from a terminal, so that a sink can be watched, a record inspected,
        and a command line tried before it is written into a tool.

        The program runs without a shell. Its two output streams are read
        concurrently, so neither can block the other, and the last line is
        kept whether or not it ended in a newline. Where the output also goes
        while the program runs is a choice of sink:

            * the console, as it arrives
            * four files beside the results, written live
            * both at once, or nowhere but the record

"""

SYNOPSIS_CLI: str = """
        hostlib run                                                             \\
            [--cwd <dir>] [--timeout <seconds>] [--env <NAME=VALUE> ...]        \\
            [--stdin <text>] [--log <prefix>] [--jsonl <file>] [--quiet] [--json]  \\
            -- <program> [<arg> ...]

        hostlib facts [--json]

        hostlib demo [--stream | --both] [--log <dir> | --no-log] [--pause <seconds>]
        hostlib demo --progress [--steps <n>] [--step <seconds>]

        hostlib [--man] [--synopsis] [--version]"""

DESCRIPTION: str = """
    DESCRIPTION

        ``hostlib run`` starts <program> with its arguments through the library,
        streams its output to the console while it runs, and exits with the
        program's own exit status. With --log the record is also written as
        four files beside the results; with --json the record is printed as
        JSON when the program ends. ``hostlib facts`` prints what the library
        knows about the host it runs on. ``hostlib demo`` runs a small batch of
        four jobs through one sink, so the bar, the streaming and the per-job
        records can be seen before they are written into a tool.

        Everything after ``--`` is the program and its arguments, exactly as
        given: no shell is involved, so a quoted argument with a space stays
        one argument and nothing is expanded. A command that needs a shell is
        written as one: ``hostlib run -- sh -c 'ls | wc -l'``.
"""

ARGS: str = """
    ARGS

        --cwd <dir>
        Run the program in <dir> rather than the current directory.

        --timeout <seconds>
        Terminate the program if it is still running after <seconds>. The
        record is marked timedOut and the exit status is 124.

        --env <NAME=VALUE>
        Set a variable in the program's environment, on top of this one.
        Repeat for several.

        --stdin <text>
        Write <text> to the program's standard input, then close it. Without
        this, standard input is connected to nothing.

        --log <prefix>
        Write the record live as <prefix>-cmd, <prefix>-stdout,
        <prefix>-stderr and <prefix>-returncode. The directory is created.

        --jsonl <file>
        Append the record to <file> as one line of JSON when the program
        ends. The directory is created. A file of such lines is what
        ``pflog read`` prints and what a log collector indexes.

        --quiet
        Do not stream the program's output to the console. The record still
        holds it.

        --json
        When the program ends, print its record as JSON on standard output.
        Combine with --quiet to get only the JSON.

        --man, --synopsis, --version
        The full manual, its first page, the version.

        demo --stream | --both
        By default the demo draws a progress bar from the batch's status and
        progress events and keeps each job's output in files. --stream shows
        every line of every job as it arrives instead; --both shows the bar
        with the lines scrolling under it.

        demo --log <dir> | --no-log
        Where the per-job records go (default ./hostlib-demo), or nowhere.

        demo --pause <seconds>
        How long each demo job spends between its lines.

        demo --progress [--steps <n>] [--step <seconds>]
        One job that loops <n> times (100), <seconds> each (0.1), redrawing a
        tqdm-style bar on its own stderr with carriage returns. The console
        sink shows it as it draws; the record afterwards holds every redraw.
"""

RECORD_HELP: str = """
    THE RECORD

        Every run produces one record, in the library a JobResult and under
        --json a JSON object, with these fields:

            status        true when the program started and exited 0
            argv          the argument list that was executed
            returncode    the exit status, or null if it never started
            stdout        the complete standard output
            stderr        the complete standard error
            errors        why a failed run failed, in words
            host          hostname, user, pid, platform, cwd, timestamp
            startedAt     when it started, ISO 8601
            endedAt       when it ended
            duration      seconds
            cwd           the working directory it ran in
            pid           the process id
            timedOut      true if --timeout terminated it

        status is never inferred from the output text.
"""

SINKS_HELP: str = """
    SINKS

        While a program runs, each chunk of its output goes to a sink. The
        library ships six: NullSink keeps nothing but the record; ConsoleSink
        streams to the terminal; JsonSink appends the record as one line of
        JSON to a file when the job ends, the form a reader or a collector
        parses and ``pflog read`` prints; FileSink writes <prefix>-cmd,
        -stdout, -stderr and -returncode live, for the case where someone
        will open the output in an editor; TeeSink fans out to several; BarSink
        draws a progress bar from the status and progress events a caller
        running many jobs emits between them. A sink is any object with six
        methods: began, stdout_write, stderr_write, status_write,
        progress_write, ended; SinkBase implements them all as no-ops.

        ``hostlib demo`` is the worked example: one batch loop, the same code
        whichever sink is attached. Its source is hostlib/cli/demo.py.
"""

EXIT_HELP: str = """
    EXIT STATUS

        ``hostlib run`` exits with the program's exit status; 127 when the
        program could not be started; 124 when it timed out; 2 on a usage
        error. ``hostlib facts`` exits 0; ``hostlib demo`` exits 1, because
        one of its jobs is meant to fail.
"""

EXAMPLES: str = """
    EXAMPLES

    Run a converter and watch it:

        hostlib run -- mri_convert in.dcm out.nii.gz

    Keep the record beside the output, in a subject's directory:

        hostlib run --log /out/sub01/mri_convert                                \\
            -- mri_convert /in/sub01/T1.dcm /out/sub01/T1.nii.gz

    A long job, bounded, with the record as JSON and nothing else printed:

        hostlib run --timeout 7200 --quiet --json                               \\
            -- recon-all -s sub01 -all

    A command that needs the shell, said so explicitly:

        hostlib run -- sh -c 'ls /in | wc -l'

    What this host is:

        hostlib facts --json

    The batch demo, with the lines scrolling under the bar:

        hostlib demo --both

    A program's own progress bar, streamed as it draws, then the record:

        hostlib demo --progress --steps 50 --step 0.05

"""


def synopsis(shortOnly: bool = False) -> str:
    """Assemble the manual text.

    Args:
        shortOnly: NAME, SYNOPSIS and a brief example only.

    Returns:
        The manual text, without the banner.
    """
    shortSynopsis: str = (
        """
    NAME

        hostlib

    SYNOPSIS
"""
        + SYNOPSIS_CLI
        + """

    BRIEF EXAMPLE

        hostlib run --log /out/job --json -- mri_convert in.dcm out.nii.gz
    """
    )
    if shortOnly:
        return shortSynopsis
    return shortSynopsis + DESCRIPTION + ARGS + RECORD_HELP + SINKS_HELP + EXIT_HELP + EXAMPLES


def manual_build() -> Manual:
    """The hostlib manual page."""
    return Manual(
        command="hostlib",
        art=BANNER_ART,
        title=BANNER_TITLE,
        text=BANNER_TEXT,
        version=__version__,
        synopsisShort=synopsis(shortOnly=True),
        synopsisFull=synopsis(shortOnly=False),
    )


def parser_build() -> argparse.ArgumentParser:
    """The command's parser: top-level manual flags, then ``run`` and ``facts``."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="hostlib",
        description="Run a program, stream its output, keep the record. Full manual: hostlib --man",
    )
    parser.add_argument("--version", action="version", version=f"hostlib {__version__}")
    parser.add_argument("--man", action="store_true", help="print the full manual")
    parser.add_argument("--synopsis", action="store_true", help="print the manual's first page")
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(dest="command")

    run: argparse.ArgumentParser = commands.add_parser("run", help="run a program through the library")
    run.add_argument("--cwd", default=None, help="working directory for the program")
    run.add_argument("--timeout", type=float, default=None, help="seconds before the program is terminated")
    run.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="set a variable")
    run.add_argument("--stdin", default=None, help="text written to the program's standard input")
    run.add_argument("--log", default=None, metavar="PREFIX", help="write the record live as four files")
    run.add_argument(
        "--jsonl", default=None, metavar="FILE", help="append the record to FILE as one line of JSON"
    )
    run.add_argument("--quiet", action="store_true", help="do not stream output to the console")
    run.add_argument("--json", action="store_true", help="print the record as JSON when the program ends")
    run.add_argument("argv", nargs=argparse.REMAINDER, help="-- program and its arguments")

    factsParser: argparse.ArgumentParser = commands.add_parser("facts", help="print the host's facts")
    factsParser.add_argument("--json", action="store_true", help="as JSON")
    demoParser_add(commands)
    return parser


def environment_parse(pairs: list[str]) -> dict[str, str]:
    """``NAME=VALUE`` strings to a dictionary.

    Raises:
        ValueError: a pair has no ``=``.
    """
    env: dict[str, str] = {}
    for pair in pairs:
        name, separator, value = pair.partition("=")
        if not separator or not name:
            raise ValueError(f"--env expects NAME=VALUE, got {pair!r}")
        env[name] = value
    return env


def sink_build(args: argparse.Namespace) -> JobSink:
    """The sink the ``run`` arguments ask for."""
    sinks: list[JobSink] = []
    if not args.quiet:
        sinks.append(ConsoleSink())
    if args.log:
        sinks.append(FileSink(args.log))
    if args.jsonl:
        sinks.append(JsonSink(args.jsonl))
    if not sinks:
        return NullSink()
    if len(sinks) == 1:
        return sinks[0]
    return TeeSink(*sinks)


def exit_forResult(result: JobResult) -> int:
    """The exit status ``hostlib run`` reports for a record."""
    if result.returncode is None:
        return EXIT_CANNOT_RUN
    if result.timedOut:
        return EXIT_TIMED_OUT
    return result.returncode


def run_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """``hostlib run``."""
    argv: list[str] = list(args.argv)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        parser.error("run: nothing to run; give the program after --")
    try:
        env: dict[str, str] = environment_parse(args.env)
    except ValueError as err:
        parser.error(str(err))
    spec: JobSpec = JobSpec(argv=argv, cwd=args.cwd, env=env or None, stdin=args.stdin, timeout=args.timeout)
    result: JobResult = job_run(spec, sink=sink_build(args))
    if args.json:
        print(result.toJson())
    elif result.returncode is None or result.timedOut:
        print("; ".join(result.errors), file=sys.stderr)
    return exit_forResult(result)


def facts_command(args: argparse.Namespace) -> int:
    """``hostlib facts``."""
    here: HostFacts = facts()
    if args.json:
        print(json.dumps(dataclasses.asdict(here), indent=4, sort_keys=True))
        return 0
    for name, value in dataclasses.asdict(here).items():
        print(f"{name:10} {value}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command.

    Args:
        argv: arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        The exit status; see EXIT STATUS in the manual.
    """
    parser: argparse.ArgumentParser = parser_build()
    args: argparse.Namespace = parser.parse_args(argv)
    if args.man or args.synopsis:
        manual_print(manual_build(), shortOnly=not args.man)
        return 0
    if args.command == "run":
        return run_command(args, parser)
    if args.command == "facts":
        return facts_command(args)
    if args.command == "demo":
        return demo_command(args)
    parser.print_help()
    return EXIT_USAGE
