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


'''Execute command in a sandbox, using 'linux-user-chroot'.

This implements an API defined in sandboxlib/__init__.py.

This backend requires the 'linux-user-chroot' program, which can only be used
with Linux. It also requires the 'unshare' program from the 'util-linux'
package, a 'mount' program that supports the `--make-rprivate` flag, and a 'sh'
program with certain standard features.

The 'linux-user-chroot' program is intended to be 'setuid', and thus usable by
non-'root' users at the discretion of the system administrator. However, the
implementation here also uses 'unshare --mount', which can only be run as
'root'. So this backend can only be run as 'root' at present. Modifying
linux-user-chroot to handle creating the new mount namespace and processing
any extra mounts would be a useful fix.

Supported mounts settings: 'undefined', 'isolated'.

Supported network settings: 'undefined', 'isolated'.

'''


import os
import textwrap

import sandboxlib


def maximum_possible_isolation():
    return {
        'mounts': 'isolated',
        'network': 'isolated',
    }


def process_mount_config(root, mounts, extra_mounts):
    # FIXME: currently errors in the generated shell script will appear in the
    # same way as errors from the actual command that the caller wanted to run.
    # That's pretty boneheaded. Could be fixed by setting a flag at the end of
    # the shell script, perhaps.

    supported_values = ['undefined', 'isolated']

    assert mounts in supported_values, \
        "'%s' is an unsupported value for 'mounts' in the " \
        "'linux-user-chroot' backend. Supported values: %s" \
        % (mounts, ', '.join(supported_values))

    extra_mounts = sandboxlib.validate_extra_mounts(extra_mounts)

    # Use 'unshare' to create a new mount namespace.
    #
    # In order to mount the things specified in 'extra_mounts' inside the
    # sandbox's mount namespace, we add a script that runs bunch of 'mount'
    # commands to the 'unshare' commandline. The mounts it creates are
    # unmounted automatically when the namespace is deleted, which is done when
    # 'unshare' exits.
    #
    # The 'undefined' and 'isolated' options are treated the same in this
    # backend, which avoids having a separate, useless code path.

    unshare_command = ['unshare', '--mount', '--', 'sh', '-e', '-c']

    # The single - is just a shell convention to fill $0 when using -c,
    # since ordinarily $0 contains the program name.
    mount_script_args = ['-']

    # This command marks any existing mounts inside the sandboxed filesystem
    # as 'private'. If they were pre-existing 'shared' or 'slave' mounts, it'd
    # be possible to change what is mounted in the sandbox from outside the
    # sandbox, or to change a mountpoint outside the sandbox from within it.
    mount_script = textwrap.dedent(r'''
        mount --make-rprivate /
        root="$1"
        shift
        ''')
    mount_script_args.append(root)

    # The rest of this script processes the items from 'extra_mounts'.
    mount_script += textwrap.dedent(r'''
    while true; do
        case "$1" in
        --)
            shift
            break
            ;;
        *)
            mount_point="$1"
            mount_type="$2"
            mount_source="$3"
            mount_options="$4"
            shift 4
            path="$root/$mount_point"
            mount -t "$mount_type" -o "$mount_options" "$mount_source" "$path"
            ;;
        esac
    done
    ''')

    for source, mount_point, mount_type, mount_options in extra_mounts:
        path = os.path.join(root, mount_point)
        if not os.path.exists(path):
            os.makedirs(path)
        mount_script_args.extend((mount_point, mount_type, source, mount_options))
    mount_script_args.append('--')

    mount_script += textwrap.dedent(r'''
    exec "$@"
    ''')

    return unshare_command + [mount_script] + mount_script_args


def process_network_config(network):
    # Network isolation is pretty easy, we 'unshare' the network namespace, and
    # nothing can access the network.

    # Network 'sharing' is a lot harder to tie down: does it just mean 'not
    # blocked'? Or does it mean 'working, with /etc/resolv.conf correctly set
    # up'? So that's not handled yet.

    supported_values = ['undefined', 'isolated']

    assert network in supported_values, \
        "'%s' is an unsupported value for 'network' in the " \
        "'linux-user-chroot' backend. Supported values: %s" \
        % (network, ', '.join(supported_values))

    if network == 'isolated':
        # This is all we need to do for network isolation
        extra_linux_user_chroot_args = ['--unshare-net']
    else:
        extra_linux_user_chroot_args = []

    return extra_linux_user_chroot_args


def run_sandbox(rootfs_path, command, cwd=None, extra_env=None,
                mounts='undefined', extra_mounts=None,
                network='undefined'):
    if type(command) == str:
        command = [command]

    linux_user_chroot_command = ['linux-user-chroot']

    unshare_command = process_mount_config(
        root=rootfs_path, mounts=mounts, extra_mounts=extra_mounts or [])

    linux_user_chroot_command += process_network_config(network)

    if cwd is not None:
        linux_user_chroot_command.extend(['--chdir', cwd])

    env = sandboxlib.environment_vars(extra_env)

    argv = (
        unshare_command + linux_user_chroot_command + [rootfs_path] + command)
    exit, out, err = sandboxlib._run_command(argv, env=env)
    return exit, out, err
