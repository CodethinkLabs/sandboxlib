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


'''Functional ('black-box') tests for all 'sandboxlib' backends.

FIXME: right now this is incomplete! Needs to introspect more!

'''


import pytest

import os

import sandboxlib


@pytest.fixture(params=['chroot', 'linux_user_chroot'])
def sandboxlib_executor(request):
    executor = getattr(sandboxlib, request.param)

    if request.param == 'chroot' and os.getuid() != 0:
        pytest.skip('chroot backend can only be used by root users')

    return executor


def test_stdout(sandboxlib_executor):
    exit, out, err = sandboxlib_executor.run_sandbox('/', ['echo', 'xyzzy'])

    assert exit == 0
    assert out.decode('unicode-escape') == 'xyzzy\n'
    assert err.decode('unicode-escape') == ''


def test_current_working_directory(sandboxlib_executor, tmpdir):
    exit, out, err = sandboxlib_executor.run_sandbox(
        '/', ['pwd'], cwd=str(tmpdir))

    assert exit == 0
    assert out.decode('unicode-escape') == '%s\n' % str(tmpdir)
    assert err.decode('unicode-escape') == ''
