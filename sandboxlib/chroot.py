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


'''Execute command in a sandbox, using 'chroot'.'''


import subprocess

import sandboxlib


def run_sandbox(rootfs_path, command, extra_env=None):
    if type(command) == str:
        command = [command]

    env = sandboxlib.BASE_ENVIRONMENT.copy()
    if extra_env is not None:
        env.update(extra_env)

    # FIXME: you gotta be root for this one.
    subprocess.call(['chroot', rootfs_path] + command)
