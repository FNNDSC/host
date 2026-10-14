host
====

``host`` runs a program, streams its output while it runs, and keeps the record of what happened: the command as run, both output streams, the exit status, and the facts of the host it ran on.

It is the one implementation of the "jobber" idea that the FNNDSC ``pf*`` and ``pl-*`` tools each used to carry a copy of. It depends on the standard library only.

.. code-block:: python

    from host import JobSpec, job_run

    result = job_run(JobSpec(argv=["mri_convert", "in.dcm", "out.nii.gz"]))
    result.status, result.returncode, result.stdout

Layout
------

``host.models``
    Dataclasses only, one module per domain. The shapes that cross a wire or land in a file.
``host.proc``
    Running things: ``job_run`` in the foreground, ``job_start`` for a handle to a background job, argv handling.
``host.sink``
    Where output goes while a job runs: a protocol and the console, file, tee and null sinks.
``host.facts``
    What the host is: hostname, user, pid, platform, cwd, time.
``host.cli``
    The ``host`` command.

Documentation in ``docs/``: ``purpose.adoc``, ``architecture.adoc``, ``history.adoc``.
