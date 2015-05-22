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


'''Execute command in a sandbox, using 'linux-user-chroot'.'''


import subprocess

import sandboxlib


def run_sandbox(rootfs_path, command, cwd=None, extra_env=None):
    if type(command) == str:
        command = [command]

    linux_user_chroot = 'linux-user-chroot'

    linux_user_chroot_args = []

    if cwd is not None:
        linux_user_chroot_args.extend(['--chdir', cwd])

    env = sandboxlib.environment_vars(extra_env)

    argv = (
        [linux_user_chroot] + linux_user_chroot_args + [rootfs_path] + command)
    subprocess.call(argv, env=env)
