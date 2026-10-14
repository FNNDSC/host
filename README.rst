hostlib
=======

**Run a program from Python, see its output as it happens, and get back a record you can trust.**

``hostlib`` is a small, dependency-free library for the one thing almost every tool eventually does and almost nobody does well: run another program. It turns the question "what happened when I ran that?" into a single typed answer, streams the program's output wherever you point it while the program is still running, and gives background jobs a handle instead of a loose process.

.. code-block:: python

    from hostlib import JobSpec, job_run

    result = job_run(JobSpec(argv=["mri_convert", "in.dcm", "out.nii.gz"]))

    result.status        # True: the program ran and exited 0
    result.returncode    # 0
    result.stdout        # everything it printed, complete
    result.stderr        # everything it complained, complete
    result.argv          # exactly what was executed
    result.host.hostname # where, by whom, when, and how long

The gap
-------

Python's ``subprocess`` is correct and complete. It is also low-level, and every program that uses it grows the same forty lines around it: split a command string, start the process, read two pipes without deadlocking, decode bytes, notice when the last line goes missing, collect the exit status, write the output somewhere sensible, remember which machine and user this was, and hand the result back as a dictionary whose keys differ from the one in the next file over.

Those forty lines are where the bugs live. A file name with a space becomes two arguments. A chatty program fills its stderr pipe and both processes wait on each other forever. Output appears only after a two-hour job finishes, or is echoed live but dropped from the record. The exit code is lost because the caller only looked at stdout. A background job is started with ``&`` inside a generated shell script and nobody ever learns whether it finished.

``hostlib`` is those forty lines written once, correctly, with a result shaped so that the caller never has to parse text to learn what happened.

The record
----------

Every run returns a ``JobResult``. It is an *envelope*: a complete, self-describing account of one execution, carrying ground truth separately from printed text.

==================  ======================================================================
``status``          ``True`` when the program started and exited 0. Never inferred from output.
``argv``            The argument list actually executed, after any splitting. No ambiguity about what ran.
``returncode``      The exit status, or ``None`` if the program could not be started.
``stdout``          The complete standard output, decoded, last line included.
``stderr``          The complete standard error, read concurrently with stdout so neither can block the other.
``errors``          Why a failed job failed, in words: ``"cannot run mri_convert: No such file or directory"``, ``"exit status 1"``, ``"timed out after 30s"``.
``hostlib``            Facts about where it ran: hostname, user, pid, platform, working directory.
``startedAt``       When it started, when it ended, and ``duration`` in seconds.
==================  ======================================================================

The envelope is a dataclass. ``dataclasses.asdict`` turns it into JSON for a log, a message queue or a web client, and the same shape reads back. The text streams are *data inside* the record, not the record itself; a program that wants to know whether something worked reads ``status`` and ``returncode``, never ``stdout``.

Running and streaming
---------------------

``job_run`` starts the program, reads both output streams concurrently until it exits, and returns the envelope. While it runs, every chunk of output also goes to a *sink*.

.. code-block:: python

    from hostlib import JobSpec, job_run
    from hostlib.sink import ConsoleSink, FileSink, TeeSink

    spec = JobSpec(argv=["recon-all", "-s", "sub01", "-all"], cwd="/work")

    # Watch a long job as it runs, and keep its record beside its results.
    result = job_run(spec, sink=TeeSink(ConsoleSink(), FileSink("/work/sub01/recon-all")))

A sink is anything with six methods: ``began`` and ``ended`` around the run, and ``stdout_write``, ``stderr_write``, ``status_write`` and ``progress_write`` during it. ``SinkBase`` implements all six as no-ops, so a custom sink overrides only what it needs. The library ships five:

``NullSink``
    The default. Output is captured into the record and nowhere else.
``ConsoleSink``
    Streams stdout and stderr to the terminal as they arrive, keeping the two apart.
``FileSink(prefix)``
    Writes ``<prefix>-cmd``, ``<prefix>-stdout``, ``<prefix>-stderr`` and ``<prefix>-returncode`` beside the job's results, live, so a crash still leaves a partial log.
``TeeSink(*sinks)``
    Fans out to several sinks at once.
``BarSink()``
    Draws a progress bar from a batch's status and progress events, and ignores the streams.

Write your own to feed a web socket, a progress bar or a log aggregator; the record you get back is the same regardless of where the output also went.

A batch, one sink
-----------------

The caller that runs many jobs is the one that knows there is a batch, so it emits the batch's progress through the same sink the jobs write into. ``BarSink`` listens to ``status_write`` and ``progress_write`` and draws one redrawn line; a console sink shows the streams; a tee shows both; the batch code is the same whichever is attached.

.. code-block:: python

    from hostlib import JobSpec, ProgressEvent, job_run
    from hostlib.sink import BarSink

    def batch_run(jobs: dict[str, JobSpec], sink) -> list:
        results = []
        total = len(jobs)
        for index, (name, spec) in enumerate(jobs.items(), start=1):
            sink.status_write(f"running {name}")
            results.append(job_run(spec, sink=sink))
            sink.progress_write(ProgressEvent("running", label=name, current=index, total=total))
        return results

    batch_run(jobs, BarSink())

``hostlib demo`` runs the complete version: four small jobs, one drawing its own carriage-return progress bar through the console sink, one failing, per-job records written beside the bar. ``--stream`` shows the lines instead of the bar, ``--both`` shows both. Its source, ``hostlib/cli/demo.py``, is the worked example.

Background jobs
---------------

``job_start`` returns a ``JobHandle`` instead of waiting.

.. code-block:: python

    from hostlib import JobSpec, job_start
    from hostlib.sink import FileSink

    handle = job_start(JobSpec(argv=["long_pipeline.sh"]), sink=FileSink("/work/run42"))

    handle.pid              # the process
    handle.poll()           # None while running, the return code once done
    handle.wait(timeout=60) # block, then
    handle.result()         # the same JobResult a foreground run returns

The handle's output is read on background threads from the moment it starts, so a background job can never stall on a full pipe, and its sink receives output while it runs. ``handle.toRecord()`` is a ``JobStarted`` dataclass, pid, argv, start time and log locations, for a service that needs to answer "what is running?" to a client.

Facts
-----

``hostlib.facts()`` returns a ``HostFacts`` dataclass: hostname, user, pid, platform, working directory and the current time. Every ``JobResult`` carries one. It is also useful on its own, wherever a program labels its output with where it came from.

Commands as text
----------------

Programs often receive the command to run as a single string. ``hostlib`` splits that string once, with ``shlex``, before anything is substituted into it, and runs the result without a shell:

.. code-block:: python

    from hostlib.proc import argv_fromTemplate

    argv = argv_fromTemplate('convert "%{in}" "%{out}"')   # ['convert', '%{in}', '%{out}']

Substitution is the caller's business (any templating library that works per argument will do); because it happens inside already-split arguments, a value containing a space, a quote or a semicolon can never change the shape of the command.

What hostlib is not
-------------------

It is not a shell: no pipes, redirection or globbing in ``argv``. A command that needs them is written explicitly as ``["sh", "-c", "..."]``, which makes the shell's involvement visible rather than implicit. It is not a scheduler, a queue or a retry loop; it runs one program and tells you what happened. It is not a replacement for ``subprocess``, which it uses underneath; it is the layer every program otherwise writes for itself on top of it.

The command
-----------

``hostlib run -- <program> [args...]`` runs a program through the library, streams its output, and exits with its status; ``--json`` prints the record. ``hostlib facts`` prints the host's facts. ``hostlib demo`` runs the batch above. All three exist to try the library from a terminal.

Install
-------

.. code-block:: console

    pip install hostlib

Python 3.11 or later, including free-threaded builds. No dependencies.

Layout
------

``hostlib.models``
    Dataclasses only, one module per domain: the shapes that cross a wire or land in a file.
``hostlib.proc``
    Running things: ``job_run``, ``job_start``, ``JobHandle``, argv handling.
``hostlib.sink``
    Where output goes while a job runs: the protocol and the four sinks.
``hostlib.facts``
    What the host is.
``hostlib.cli``
    The ``hostlib`` command.

``docs/purpose.adoc``, ``docs/architecture.adoc`` and ``docs/history.adoc`` describe why the library exists, how it is built, and where it came from.

Licence
-------

MIT.
