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
import pipes
import subprocess
import warnings


class ProgramNotFound(Exception):
    pass


def degrade_config_for_capabilities(in_config, warn=True):
    '''Alter settings in 'in_config' that a given backend doesn't support.

    This function is provided for users who want to be flexible about which
    sandbox implementation they use, and who don't mind if not all of the
    isolation that they requested is actually possible.

    This is not a general purpose 'check your config' function. Any unexpected
    keys or values in ``in_config`` will just be ignored.

    If 'warn' is True, each change the function makes is logged using
    warnings.warn().

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
      - extra_mounts: a list of locations to mount inside 'rootfs_path',
            specified as a list of tuples of (source_path, target_path, type,
            options). The 'type' and 'options' should match what would be
            specified in /etc/fstab, but a backends may support only a limited
            subset of values. The 'target_path' is relative to filesystem_root
            and will be created before mounting if it doesn't exist.
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


def get_executor(name):
    '''Return the execution module with the given name.

    KeyError is raised if the backend isn't found.

    This function will, for convenience, convert '-' to '_'. This means
    "linux-user-chroot" will return the "linux_user_chroot" backend, instead of
    raising an error.

    '''

    name = name.replace('-', '_')

    try:
        executor = getattr(sandboxlib, name)
    except AttributeError:
        raise KeyError(
            "%s is not a known executor in this version of 'sandboxlib'." %
            name)

    return executor


def executor_for_platform():
    '''Returns an execution module that will work on the current platform.

    The autodetection can be overridden by setting SANDBOXLIB_BACKEND in the
    environment of the process, which can be useful for testing and debugging.

    '''

    log = logging.getLogger("sandboxlib")

    backend = None

    if 'SANDBOXLIB_BACKEND' in os.environ:
        backend_name = os.environ['SANDBOXLIB_BACKEND']
        logging.info("Got %s from SANDBOXLIB_BACKEND variable.", backend_name)
        try:
            backend = get_executor(backend_name)
        except KeyError:
            warnings.warn(
                "SANDBOXLIB_BACKEND environment variable is set to an invalid "
                "value %s." % backend_name)

    if backend is None and platform.uname()[0] == 'Linux':
        log.info("Linux detected, looking for 'linux-user-chroot'.")
        try:
            program = sandboxlib.linux_user_chroot.linux_user_chroot_program()
            log.info("Found %s, choosing 'linux_user_chroot' module.", program)
            backend = sandboxlib.linux_user_chroot
        except sandboxlib.ProgramNotFound as e:
            log.debug("Did not find 'linux-user-chroot': %s", e)

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
        if mount_entry[1] is None:
            raise AssertionError(
                "Mount point empty in mount entry %s" % mount_entry)

        if len(mount_entry) == 3:
            full_mount_entry = list(mount_entry) + ['']
        elif len(mount_entry) == 4:
            full_mount_entry = list(mount_entry)
        else:
            raise AssertionError(
                "Invalid mount entry in 'extra_mounts': %s" % mount_entry)

        # Convert all the entries to strings to prevent type errors later
        # on. None is special cased to the empty string, as str(None) is
        # "None". It's valid for some parameters to be '' in some cases.
        processed_mount_entry = []
        for item in full_mount_entry:
            if item is None:
                processed_mount_entry.append('')
            else:
                processed_mount_entry.append(str(item))

        new_extra_mounts.append(processed_mount_entry)

    return new_extra_mounts



def argv_to_string(argv):
    return ' '.join(map(pipes.quote, argv))


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

    log = logging.getLogger('sandboxlib')
    log.debug('Running: %s', argv_to_string(argv))

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
import sandboxlib.utils
