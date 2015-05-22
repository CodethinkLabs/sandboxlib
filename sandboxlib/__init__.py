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


'''sandboxlib module.'''


BASE_ENVIRONMENT = {
    # Mandated by https://github.com/appc/spec/blob/master/SPEC.md#execution-environment
    'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
}


def environment_vars(extra_env=None):
    '''Return the complete set of environment variables for a sandbox.

    The base environment is defined above, and callers can add extra variables
    to this or override the defaults by passing a dict to 'extra_env'.

    '''
    env = BASE_ENVIRONMENT.copy()

    if extra_env is not None:
        env.update(extra_env)

    return env


# Executors
import sandboxlib.chroot
import sandboxlib.linux_user_chroot

import sandboxlib.load
