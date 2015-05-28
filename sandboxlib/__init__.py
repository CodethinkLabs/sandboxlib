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


'''sandboxlib module.

This module contains multiple 'executor' backends, which must all provide
the same API. A stub version of the API is defined in this file, with
docstrings that describe the different parameters.

'''


import logging
import os
import platform
import shutil
import subprocess
import sys


def maximum_possible_isolation():
    '''Describe the 'tightest' isolation possible with a specific backend.

    This function returns a dict, with the following keys:

      - mounts
      - network

    Each key maps to a parameter of the run_sandbox() function, and each
    value is a valid value for that parameter.

    Example result:

        {
            'mounts': 'undefined'
            'network': 'isolated'
        }

    You can pass the result directly to a run_sandbox() function directly,
    using the `**` operator to turn it into keyword arguments as in the
    following example:

        isolation_settings = maximum_possible_isolation()
        run_sandbox(root_path, ['echo', 'hello'], **isolation_settings)

    '''
    raise NotImplementedError()



# Special value for 'stderr' and 'stdout' parameters to indicate 'capture
# and return the data'.
CAPTURE = subprocess.PIPE

# Special value for 'stderr' parameter to indicate 'forward to stdout'.
STDOUT = subprocess.STDOUT


def run_sandbox(command, cwd=None, env=None,
                filesystem_root='/', filesystem_writable_paths='all',
                mounts='undefined', extra_mounts=None,
                network='undefined',
                stderr=CAPTURE, stdout=CAPTURE):
    '''Run 'command' in a sandboxed environment.

    Parameters:
      - command: the command to run. Pass a list of parameters rather than
            using spaces to separate them, e.g. ['echo', '"Hello world"'].
      - cwd: the working directory of 'command', relative to 'rootfs_path'.
            Defaults to '/' if "rootfs_path" is specified, and the current
            directory of the calling process otherwise.
      - env: environment variables to set
      - filesystem_root: the path to the root of the sandbox. Defaults to '/',
            which doesn't isolate the command from the host filesystem at all.
      - filesystem_writable_paths: defaults to 'all', which allows the command
            to write to anywhere under 'filesystem_root' that the user of the
            calling process could write to. Backends may accept a list of paths
            instead of 'all', and will prevent writes to any files not under a
            path in that whitelist. If 'none' or an empty list is passed, the
            whole file-system will be read-only. The paths should be relative
            to filesystem_root. This will processed /after/ extra_mounts are
            mounted.
      - mounts: configures mount sharing. Defaults to 'undefined', where no
            no attempt is made to isolate mounts. Backends may support
            'isolated' as well.
      - extra_mounts: a list of locations to mount inside 'rootfs_path', with
            type and options specified in a backend-specific way.
      - network: configures network sharing. Defaults to 'undefined', where
            no attempt is made to either prevent or provide networking
            inside the sandbox. Backends may support 'isolated' and/or other
            values as well.
      - stdout: whether to capture stdout, or redirect stdout to a file handle.
            If set to sandboxlib.CAPTURE, the function will return the stdout
            data, if not, it will return None for that. If stdout=None, the
            data will be discarded -- it will NOT inherit the parent process's
            stdout, unlike with subprocess.Popen(). Set 'stdout=sys.stdout' if
            you want that.
      - stderr: same as stdout

    Returns:
      a tuple of (exit code, stdout output, stderr output).

    '''
    raise NotImplementedError()


def run_sandbox_with_redirection(command, **sandbox_config):
    '''Start a subprocess in a sandbox, redirecting stderr and/or stdout.

    The sandbox_config arguments are the same as the run_command() function.

    This returns just the exit code, because if stdout or stderr are redirected
    those values will be None in any case.

    '''
    raise NotImplementedError()


def find_program(program_name):
    # Python 3.3 and newer provide a 'find program in PATH' function. Otherwise
    # we fall back to the `which` program.
    if sys.version_info.major >= 3 and sys.version_info.minor >= 3:
        program_path = shutil.which(program_name)
    else:
        try:
            argv = ['which', program_name]
            program_path = subprocess.check_output(argv).strip()
        except subprocess.CalledProcessError as e:
            logging.debug("Error searching for %s: %s", program_name, e)
            program_path = None
    return program_path


def sandbox_module_for_platform():
    '''Returns an execution module that will work on the current platform.'''

    log = logging.getLogger("sandboxlib")

    backend = None

    if platform.uname() == 'Linux':
        log.info("Linux detected, looking for 'linux-user-chroot'.")
        linux_user_chroot_program = find_program('linux-user-chroot')
        if linux_user_chroot_program is not None:
            log.info("Found %s, choosing 'linux_user_chroot' module.",
                     linux_user_chroot_program)
            backend = sandboxlib.linux_user_chroot
        else:
            log.debug("Did not find 'linux-user-chroot' program in PATH.")

    if backend is None:
        log.info("Choosing 'chroot' sandbox module.")
        backend = sandboxlib.chroot

    return backend


def validate_extra_mounts(extra_mounts):
    '''Validate and fill in default values for 'extra_mounts' setting.'''
    if extra_mounts == None:
        return []

    new_extra_mounts = []

    for mount_entry in extra_mounts:
        if len(mount_entry) == 3:
            new_mount_entry = list(mount_entry) + ['']
        elif len(mount_entry) == 4:
            new_mount_entry = list(mount_entry)
        else:
            raise AssertionError(
                "Invalid mount entry in 'extra_mounts': %s" % mount_entry)

        if new_mount_entry[0] is None:
            new_mount_entry[0] = ''
            #new_mount_entry[0] = 'none'
        if new_mount_entry[2] is None:
            new_mount_entry[2] = ''
        if new_mount_entry[3] is None:
            new_mount_entry[3] = ''
        new_extra_mounts.append(new_mount_entry)

    return new_extra_mounts


def _run_command(argv, stdout, stderr, cwd=None, env=None):
    '''Wrapper around subprocess.Popen() with common settings.

    This function blocks until the subprocess has terminated.

    Unlike the subprocess.Popen() function, if stdout or stderr are None then
    output is discarded.

    It then returns a tuple of (exit code, stdout output, stderr output).
    If stdout was not equal to subprocess.PIPE, stdout will be None. Same for
    stderr.

    '''
    if stdout is None or stderr is None:
        dev_null = open(os.devnull, 'w')
        stdout = stdout or dev_null
        stderr = stderr or dev_null
    else:
        dev_null = None

    try:
        process = subprocess.Popen(
            argv,
            # The default is to share file descriptors from the parent process
            # to the subprocess, which is rarely good for sandboxing.
            close_fds=True,
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=stderr,
        )

        # The 'out' variable will be None unless subprocess.PIPE was passed as
        # 'stdout' to subprocess.Popen(). Same for 'err' and 'stderr'. If
        # subprocess.PIPE wasn't passed for either it'd be safe to use .wait()
        # instead of .communicate(), but if they were then we must use
        # .communicate() to avoid blocking the subprocess if one of the pipes
        # becomes full. It's safe to use .communicate() in all cases.

        out, err = process.communicate()
    finally:
        if dev_null is not None:
            dev_null.close()

    return process.returncode, out, err


# Executors
import sandboxlib.chroot
import sandboxlib.linux_user_chroot

import sandboxlib.load
