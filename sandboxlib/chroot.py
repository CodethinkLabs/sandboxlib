# Copyright (C) 2015  Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.


'''Execute command in a sandbox, using os.chroot().

This implements an API defined in sandboxlib/__init__.py.

This backend should work on any POSIX-compliant operating system. It has been
tested on Linux only. The calling process must be able to use the chroot()
syscall, which is likely to require 'root' priviliges.

Supported network settings: 'undefined'.

The code would be simpler if we just used the 'chroot' program, but it's not
always practical to do that. First, it may not be installed. Second, we can't
set the working directory of the program inside the chroot, unless we assume
that the sandbox contains a shell and we do some hack like running
`/bin/sh -c "cd foo && command"`. It's better to call the kernel directly.

'''


import multiprocessing
import os

import sandboxlib


def maximum_possible_isolation():
    return {
        'network': 'undefined'
    }


def process_network_config(network):
    # It'd be possible to implement network isolation on Linux using the
    # clone() syscall. However, I prefer to have the 'chroot' backend behave
    # the same on all platforms, and have separate Linux-specific backends to
    # do Linux-specific stuff.

    assert network == 'undefined', \
        "'%s' is an unsupported value for 'network' in the 'chroot' backend. " \
        "Network sharing cannot be be configured in this backend." % network


def _run_command_in_chroot(pipe, rootfs_path, command, cwd, env):
    # This function should be run in a multiprocessing.Process() subprocess,
    # because it calls os.chroot(). There's no 'unchroot()' function! After
    # chrooting, it calls sandboxlib._run_command(), which uses the
    # 'subprocess' module to exec 'command'. This means there are actually
    # two subprocesses, which is not ideal, but it seems to be the simplest
    # implementation.
    #
    # An alternative approach would be to use the 'preexec_fn' feature of
    # subprocess.Popen() to call os.chroot(rootfs_path) and os.chdir(cwd).
    # The Python 3 '_posixsubprocess' module hints in several places that
    # deadlocks can occur when using preexec_fn, and it is very difficult to
    # propagate exceptions from that function, so it seems best to avoid it.

    try:
        # You have most likely got to be the 'root' user in order for this to
        # work.
        try:
            os.chroot(rootfs_path)
        except OSError as e:
            raise RuntimeError("Unable to chroot: %s" % e)

        if cwd is not None:
            os.chdir(cwd)

        exit, out, err = sandboxlib._run_command(command, env=env)
        pipe.send([exit, out, err])
        os._exit(0)
    except Exception as e:
        pipe.send(e)
        os._exit(1)


def run_sandbox(rootfs_path, command, cwd=None, extra_env=None,
                network='undefined'):
    if type(command) == str:
        command = [command]

    env = sandboxlib.environment_vars(extra_env)

    process_network_config(network)

    pipe_parent, pipe_child = multiprocessing.Pipe()

    process = multiprocessing.Process(
        target=_run_command_in_chroot,
        args=(pipe_child, rootfs_path, command, cwd, env))
    process.start()
    process.join()

    if process.exitcode == 0:
        exit, out, err = pipe_parent.recv()
        return exit, out, err
    else:
        # Note that no effort is made to pass on the original traceback, which
        # will be within the _run_command_in_chroot() function somewhere.
        exception = pipe_parent.recv()
        raise exception
