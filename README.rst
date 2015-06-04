============================================================================
sandboxlib: a lightweight library for running programs/commands in a sandbox
============================================================================

This project is a total work in progress, no documentation yet.

It is being developed as part of the Baserock_ project.

The goal of this library is to provide the sandboxing functionality that is
already present in the build tools Morph_ and YBD_. We want this new library
to be usable without depending on linux-user-chroot_, so that it can be used
on Mac OS X, and hopefully other platforms too.

A longer term goal is to become a useful, generic, cross-platform tool for
running commands in an environment that is partially isolated from the host
system in some way.

The library is implemented in Python currently. This is mostly because it is
an adaptation of existing Python code, not because of any desire to exclude
other languages. Maybe we could rewrite it as a C library with Python bindings.

SANDBOXLIB DOES NOT GUARANTEE YOU ANY KIND OF SECURITY. Its main purpose is
for isolating software builds from the host system, to ensure that builds
are not contacting the network, or reading or writing files outside the build
environment.

.. _Baserock: http://www.baserock.org/
.. _Morph: http://wiki.baserock.org/Morph/
.. _YBD: https://github.com/devcurmudgeon/ybd/
.. _linux-user-chroot: https://git.gnome.org/browse/linux-user-chroot/tree/

Current backends
================

- chroot: any POSIX OS
- linux-user-chroot_ (plus ``unshare``): Linux-only

Possible future backends
========================

- `Security Enhanced Linux`_ (SELinux): see https://danwalsh.livejournal.com/28545.html
- systemd-nspawn_

.. _Security Enhanced Linux: http://selinuxproject.org/page/Main_Page
.. _systemd-nspawn: http://www.freedesktop.org/software/systemd/man/systemd-nspawn.html

Relationship to other projects
==============================

Sandboxing
----------

libsandbox / pysandbox
~~~~~~~~~~~~~~~~~~~~~~

The libsandbox_ library is a Linux-specific implementation of process
sandboxing, which supports intercepting syscalls, calling setrlimit(),
and dropping certain privileges.

.. _libsandbox: https://github.com/openjudge/sandbox

PRoot
~~~~~

The PRoot_ tool provids features similar to linux-user-chroot_, plus some
extra code to allow running programs for a different architecture using
virtualisation. The PRoot tool is `discontinued <https://plus.google.com/107605112469213359575/posts/NA5GxX2DAHe>`_.

.. _PRoot: http://proot.me/

seccomp
~~~~~~~

The Linux kernel provides seccomp_ mode. This is a very restrictive sandbox
in which most programs would not work at all. It is `used by Google Chrome
<https://code.google.com/p/chromium/wiki/LinuxSandboxing#The_seccomp-bpf_sandbox>`_,
among other things.

.. _seccomp: https://en.wikipedia.org/wiki/Seccomp

Further reading
~~~~~~~~~~~~~~~

- `Sandboxing for multi-tenant applications <https://web.archive.org/web/20121129121538/http://blog.technologyofcontent.com/2011/04/sandboxing-for-multi-tenant-applications>`_ (archived)
- `StackOverflow question "Run an untrusted C program in a sandbox in Linux that prevents it from opening files, forking, etc.? <https://stackoverflow.com/questions/4249063/run-an-untrusted-c-program-in-a-sandbox-in-linux-that-prevents-it-from-opening-f>`_
- `StackOverflow question "How to "jail" a process without being root? <https://unix.stackexchange.com/questions/6433/how-to-jail-a-process-without-being-root>`_

Containerisation
----------------

There is a lot of overlap between the topics of 'containerisation' and
'sandboxing'. Many tools that work with 'containers' expect that containers
are long-lived things, where the 'sandboxlib' library treats a sandbox as a
much more lightweight, temporary thing.

App Container spec
~~~~~~~~~~~~~~~~~~

I have been using the `App Container spec`_ as a reference during development.
The scope of 'sandboxlib' is different to that of the App Container spec:
'sandboxlib' only deals with a single, isolated sandbox (which may or may
not be a 'container'), where the App Container spec is focused on multiple
containers. However, 'sandboxlib' would be a useful building block for
implementing a complete App Container runtime, and simple App Container images
(.acis) should be runnable with the ``run-sandbox`` tool directly.

.. _App Container spec: https://github.com/appc/spec/

Docker
~~~~~~

Docker_ allows managing multiple prebuilt container systems. While it `can
support multiple platform-specific backends <https://blog.docker.com/2014/03/docker-0-9-introducing-execution-drivers-and-libcontainer/>`_
for running containers, I am only aware of Linux-specific backends at the time
of writing.

.. _Docker: http://www.docker.io/

schroot
~~~~~~~

The use case for the schroot_ tool is 'I want to define a contained
environment once, and use it many times.' The 'sandboxlib' library is more
about dynamically creating sandboxes. If schroot_ suits your needs, just
use it directly without any abstraction layer.

.. _schroot: https://launchpad.net/schroot

Python-specific Sandboxing
--------------------------

The 'sandboxlib' library is for sandboxing *any* program, at the operating
system level.

If you want to do language-level sandboxing (i.e. run untrusted Python code
within a larger Python program), there are some ways to do it.

The concensus seems to be that Python language-level sandboxing is pretty much
impossible with the default 'cpython' Python runtime:

- https://mail.python.org/pipermail/python-dev/2013-November/130132.html
- https://programmers.stackexchange.com/questions/191623/best-practices-for-execution-of-untrusted-code

However, other Python runtimes do support language-level sandboxing. PyPy_ is one:

- https://pypy.readthedocs.org/en/latest/sandbox.html

.. _PyPy: http://www.pypy.org/

Build tools
-----------

Bazel
~~~~~

The Bazel_ build tool contains a `Linux-specific sandbox implementation
<https://github.com/google/bazel/blob/master/src/main/tools/namespace-sandbox.c>`_.

.. _Bazel: http://bazel.io/

Morph
~~~~~

The Morph_ build tool (from Baserock_) is the original source of the
'sandboxlib' linux_user_chroot backend. Hopefully Morph will adopt the
'sandboxlib' library in future.

YBD
~~~

The YBD_ build tool (from Baserock_) `triggered the creation of the
'sandboxlib' library <https://github.com/devcurmudgeon/ybd/issues/32>`_.

License
-------

License is GPLv2 but other licensing can be considered on request

Most of the copyright is currently Codethink but don't let that put you off.
There's no intent to keep this as a Codethink-only project, nor will there be
any attempt to get folks to sign a contributor agreement. Contributors retain
their own copyright.
