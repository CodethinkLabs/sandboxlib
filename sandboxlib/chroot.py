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
tested on Linux and Mac OS X. The calling process must be able to use the
chroot() syscall, which is likely to require 'root' priviliges.

If any 'extra_mounts' are specified, there must be a working 'mount' binary in
the host system.

The code would be simpler if we just used the 'chroot' program, but it's not
always practical to do that. First, it may not be installed. Second, we can't
set the working directory of the program inside the chroot, unless we assume
that the sandbox contains a shell and we do some hack like running
`/bin/sh -c "cd foo && command"`. It's better to call the kernel directly.

'''


import contextlib
import multiprocessing
import os
import subprocess
import warnings

import sandboxlib


CAPABILITIES = {
    'network': ['undefined'],
    'mounts': ['undefined'],
    'filesystem_writable_paths': ['all'],
}


def degrade_config_for_capabilities(in_config, warn=True):
    # Currently this is all done manually... it may make sense to add something
    # in utils.py that automatically checks the config against CAPABILITIES.
    out_config = in_config.copy()

    def degrade_and_warn(name, allowed_value):
        if warn:
            backend = 'chroot'
            value = out_config[name]
            msg = (
                'Unable to set %(name)s=%(value)s in a %(backend)s sandbox, '
                'falling back to %(name)s=%(allowed_value)s' % locals())
            warnings.warn(msg)
        out_config[name] = allowed_value

    if out_config.get('mounts', 'undefined') != 'undefined':
        degrade_and_warn('mounts', 'undefined')

    if out_config.get('network', 'undefined') != 'undefined':
        degrade_and_warn('network', 'undefined')

    if out_config.get('filesystem_writable_paths', 'all') != 'all':
        degrade_and_warn('filesystem_writable_paths', 'all')

    return out_config


def process_mount_config(mounts, extra_mounts):
    assert mounts == 'undefined', \
        "'%s' is an unsupported value for 'mounts' in the 'chroot' " \
        "Mount sharing cannot be configured in this backend." % mounts

    extra_mounts = sandboxlib.validate_extra_mounts(extra_mounts)

    return extra_mounts


def process_network_config(network):
    assert network == 'undefined', \
        "'%s' is an unsupported value for 'network' in the 'chroot' backend. " \
        "Network sharing cannot be be configured in this backend." % network


def process_writable_paths(fs_root, writable_paths):
    assert writable_paths == 'all'


def mount(source, path, mount_type, mount_options):
    # We depend on the host system's 'mount' program here, which is a
    # little sad. It's possible to call the libc's mount() function
    # directly from Python using the 'ctypes' library, and perhaps we
    # should do that instead.
    argv = [
        'mount', '-t', mount_type, '-o', mount_options, source, path]
    exit, out, err = sandboxlib._run_command(
        argv, stdout=sandboxlib.CAPTURE, stderr=sandboxlib.CAPTURE)

    if exit != 0:
        raise RuntimeError(
            "%s failed: %s" % (
                argv, err.decode('utf-8')))


def unmount(path):
    argv = ['umount', path]
    exit, out, err = sandboxlib._run_command(
        argv, stdout=sandboxlib.CAPTURE, stderr=sandboxlib.CAPTURE)

    if exit != 0:
        warnings.warn("%s failed: %s" % (
            argv, err.decode('utf-8')))


@contextlib.contextmanager
def mount_all(rootfs_path, mount_info_list):
    mounted = []

    try:
        for source, mount_point, mount_type, mount_options in mount_info_list:
            # Strip the preceeding '/' from mount_point, because it'll break
            # os.path.join().
            mount_point_no_slash = os.path.relpath(mount_point, start='/')

            path = os.path.join(rootfs_path, mount_point_no_slash)
            if not os.path.exists(path):
                os.makedirs(path)

            mount(source, path, mount_type, mount_options)
            mounted.append(path)

        yield
    finally:
        for mountpoint in mounted:
            unmount(mountpoint)


def run_command_in_chroot(pipe, stdout, stderr, extra_mounts, chroot_path,
                          command, cwd, env):
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
            os.chroot(chroot_path)
        except OSError as e:
            raise RuntimeError("Unable to chroot: %s" % e)

        # This is important in case 'cwd' is a relative path.
        os.chdir('/')

        if cwd is not None:
            try:
                os.chdir(cwd)
            except OSError as e:
                raise RuntimeError(
                    "Unable to set current working directory: %s" % e)

        exit, out, err = sandboxlib._run_command(
            command, stdout, stderr, env=env)
        pipe.send([exit, out, err])
        result = 0
    except Exception as e:
        pipe.send(e)
        result = 1
    os._exit(result)


def run_sandbox(command, cwd=None, env=None,
                filesystem_root='/', filesystem_writable_paths='all',
                mounts='undefined', extra_mounts=None,
                network='undefined',
                stdout=sandboxlib.CAPTURE, stderr=sandboxlib.CAPTURE):
    if type(command) == str:
        command = [command]

    extra_mounts = process_mount_config(mounts, extra_mounts)

    process_network_config(network)

    process_writable_paths(filesystem_root, filesystem_writable_paths)

    pipe_parent, pipe_child = multiprocessing.Pipe()

    with mount_all(filesystem_root, extra_mounts):
        process = multiprocessing.Process(
            target=run_command_in_chroot,
            args=(pipe_child, stdout, stderr, extra_mounts, filesystem_root,
                  command, cwd, env))
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


def run_sandbox_with_redirection(command, **sandbox_config):
    exit, out, err = run_sandbox(command, **sandbox_config)
    # out and err will be None
    return exit
