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

This backend requires the `linux-user-chroot` program. This program is
Linux-only. It is intended to be a 'setuid', and thus usable by non-'root'
users that have explicitly been given permission to use it.

Supported network settings: 'undefined', 'isolated'.

'''


import sandboxlib


def maximum_possible_isolation():
    return {
        'network': 'isolated',
    }


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
                network='undefined'):
    if type(command) == str:
        command = [command]

    linux_user_chroot = 'linux-user-chroot'

    linux_user_chroot_args = []

    linux_user_chroot_args += process_network_config(network)

    if cwd is not None:
        linux_user_chroot_args.extend(['--chdir', cwd])

    env = sandboxlib.environment_vars(extra_env)

    argv = (
        [linux_user_chroot] + linux_user_chroot_args + [rootfs_path] + command)
    exit, out, err = sandboxlib._run_command(argv, env=env)
    return exit, out, err
