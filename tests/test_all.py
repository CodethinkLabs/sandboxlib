# Copyright (C) 2015-2016  Codethink Limited
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


'''Functional ('black-box') tests for all 'sandboxlib' backends.'''


import pytest

import os

import sandboxlib
from programs import (
    file_is_writable_test_program, file_or_directory_exists_test_program,
    session_tmpdir)


@pytest.fixture(params=['chroot', 'linux_user_chroot', 'bubblewrap'])
def sandboxlib_executor(request):
    executor = getattr(sandboxlib, request.param)

    if request.param == 'chroot' and os.getuid() != 0:
        pytest.skip('chroot backend can only be used by root users')

    return executor


def test_no_output(sandboxlib_executor):
    '''Test ignoring of stderr/stdout.

    We could use run_sandbox_with_redirection() and not get the 'err' and 'out'
    parameters at all, but we may as well test that they are indeed None.

    '''
    exit, out, err = sandboxlib_executor.run_sandbox(
        ['echo', 'xyzzy'], stdout=None, stderr=None)

    assert exit == 0
    assert out is None
    assert err is None

def test_output(sandboxlib_executor):
    exit, out, err = sandboxlib_executor.run_sandbox(['echo', 'xyzzy'])

    assert exit == 0
    assert out.decode('unicode-escape') == 'xyzzy\n'
    assert err.decode('unicode-escape') == ''

    exit, out, err = sandboxlib_executor.run_sandbox(
        ['sh', '-c', 'echo xyzzy >&2; exit 11'])

    assert exit == 11
    assert out.decode('unicode-escape') == ''
    assert err.decode('unicode-escape') == 'xyzzy\n'

def test_output_redirection(sandboxlib_executor, tmpdir):
    outlog_fp = str(tmpdir.join('outlog.txt'))
    errlog_fp = str(tmpdir.join('errlog.txt'))
    with open(outlog_fp, 'w') as outlog, open(errlog_fp, 'w') as errlog:
        exit = sandboxlib_executor.run_sandbox_with_redirection(
             ['sh', '-c', 'echo abcde; echo xyzzy >&2'],
             stdout=outlog, stderr=errlog)

    with open(outlog_fp) as outlog, open(errlog_fp) as errlog:
        assert outlog.read() == 'abcde\n'
        assert errlog.read() == 'xyzzy\n'

    with open(outlog_fp, 'w') as outlog, open(errlog_fp, 'w') as errlog:
        exit = sandboxlib_executor.run_sandbox_with_redirection(
             ['sh', '-c', 'echo abcde; echo xyzzy >&2'],
             stdout=outlog, stderr=sandboxlib.STDOUT)

    with open(outlog_fp) as outlog:
        assert outlog.read() == 'abcde\nxyzzy\n'

def test_current_working_directory(sandboxlib_executor, tmpdir):
    exit, out, err = sandboxlib_executor.run_sandbox(
        ['pwd'], cwd=str(tmpdir))

    assert exit == 0
    assert out.decode('unicode-escape') == '%s\n' % str(tmpdir)
    assert err.decode('unicode-escape') == ''

def test_environment(sandboxlib_executor):
    exit, out, err = sandboxlib_executor.run_sandbox(
        ['env'], env={'foo': 'bar'})

    assert exit == 0
    assert out.decode('unicode-escape') == 'foo=bar\n'
    assert err.decode('unicode-escape') == ''

def test_isolated_mounts(sandboxlib_executor):
    if sandboxlib_executor == sandboxlib.chroot:
        pytest.skip('chroot backend does not support mounts isolation')
    elif sandboxlib_executor == sandboxlib.linux_user_chroot:
       # linux-user-chroot always creates a new mount namespace
       pass

def test_isolated_network(sandboxlib_executor):
    if sandboxlib_executor == sandboxlib.chroot:
        pytest.skip('chroot backend does not support network isolation')

    exit, out, err = sandboxlib_executor.run_sandbox(
        ['sh', '-c', 'cat /proc/net/dev | sed 1,2d | cut -f1 -d:'],
        network='isolated')

    assert exit == 0
    assert out.decode('unicode-escape').strip() == 'lo'
    assert err.decode('unicode-escape') == ''


class TestMounts(object):
    @pytest.fixture()
    def mounts_test_sandbox(self, tmpdir,
                            file_or_directory_exists_test_program):
        sandbox_path = tmpdir.mkdir('sandbox')

        bin_path = sandbox_path.mkdir('bin')

        file_or_directory_exists_test_program.copy(bin_path)
        bin_path.join('test-file-or-directory-exists').chmod(0o755)

        return sandbox_path

    def test_mount_proc(self, sandboxlib_executor, mounts_test_sandbox):
        exit, out, err = sandboxlib_executor.run_sandbox(
            ['/bin/test-file-or-directory-exists', '/proc'],
            filesystem_root=str(mounts_test_sandbox),
            extra_mounts=[(None, '/proc', 'proc')])

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == "/proc exists"
        assert exit == 0

    def test_mount_tmpfs(self, sandboxlib_executor, mounts_test_sandbox):
        exit, out, err = sandboxlib_executor.run_sandbox(
            ['/bin/test-file-or-directory-exists', '/dev/shm'],
            filesystem_root=str(mounts_test_sandbox),
            extra_mounts=[(None, '/dev/shm', 'tmpfs')])

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == "/dev/shm exists"
        assert exit == 0

    def test_invalid_mount_specs(self, sandboxlib_executor):
        with pytest.raises(AssertionError) as excinfo:
            exit, out, err = sandboxlib_executor.run_sandbox(
                ['true'], extra_mounts=[('proc', None, 'tmpfs')])

            assert excinfo.value.message == (
                "Mount point empty in mount entry ('proc', None, 'tmpfs')")

        with pytest.raises(AssertionError) as excinfo:
            exit, out, err = sandboxlib_executor.run_sandbox(
                ['true'], extra_mounts=[('proc', 'tmpfs')])

            assert excinfo.value.message == (
                "Invalid mount entry in 'extra_mounts': ('proc', 'tmpfs')")


class TestWriteablePaths(object):
    @pytest.fixture()
    def writable_paths_test_sandbox(self, tmpdir,
                                    file_is_writable_test_program):
        sandbox_path = tmpdir.mkdir('sandbox')

        bin_path = sandbox_path.mkdir('bin')

        file_is_writable_test_program.copy(bin_path)
        bin_path.join('test-file-is-writable').chmod(0o755)

        data_path = sandbox_path.mkdir('data')
        data_path = data_path.mkdir('1')
        data_path.join('canary').write("Please don't overwrite me.")

        return sandbox_path

    def test_none_writable(self, sandboxlib_executor,
                           writable_paths_test_sandbox):
        if sandboxlib_executor == sandboxlib.chroot:
            pytest.xfail("chroot backend doesn't support read-only paths.")

        exit, out, err = sandboxlib_executor.run_sandbox(
            ['/bin/test-file-is-writable', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths='none')

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Couldn't open /data/1/canary for writing."
        assert exit == 1

    def test_some_writable(self, sandboxlib_executor,
                           writable_paths_test_sandbox):
        if sandboxlib_executor == sandboxlib.chroot:
            pytest.xfail("chroot backend doesn't support read-only paths.")

        exit, out, err = sandboxlib_executor.run_sandbox(
            ['/bin/test-file-is-writable', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths=['/data/1'])

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Wrote data to /data/1/canary."
        assert exit == 0

    def test_all_writable(self, sandboxlib_executor,
                          writable_paths_test_sandbox):
        exit, out, err = sandboxlib_executor.run_sandbox(
            ['/bin/test-file-is-writable', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths='all')

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Wrote data to /data/1/canary."
        assert exit == 0

    def test_mount_point_not_writable(self, sandboxlib_executor,
                                      writable_paths_test_sandbox):
        if sandboxlib_executor == sandboxlib.chroot:
            pytest.xfail("chroot backend doesn't support read-only paths.")

        exit, out, err = sandboxlib_executor.run_sandbox(
            ['/bin/test-file-is-writable', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths='none')

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Couldn't open /data/1/canary for writing."
        assert exit == 1

    def test_mount_point_writable(self, sandboxlib_executor,
                                  writable_paths_test_sandbox):
        if sandboxlib_executor == sandboxlib.chroot:
            pytest.xfail("chroot backend doesn't support read-only paths.")

        exit, out, err = sandboxlib_executor.run_sandbox(
            ['/bin/test-file-is-writable', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths=['/data'])

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Wrote data to /data/1/canary."
        assert exit == 0


def test_executor_for_platform():
    '''Simple test of backend autodetection.'''
    executor = sandboxlib.executor_for_platform()
    test_output(executor)

def test_sandboxlib_backend_env_var(sandboxlib_executor):
    executor_name = sandboxlib_executor.__name__.split('.')[-1]
    os.environ["SANDBOXLIB_BACKEND"] = executor_name
    executor = sandboxlib.executor_for_platform()
    assert executor == sandboxlib_executor

def test_sandboxlib_backend_env_var_unknown_executor():
    executor = sandboxlib.executor_for_platform()
    os.environ["SANDBOXLIB_BACKEND"] = "unknown"
    assert executor == sandboxlib.executor_for_platform()

def test_degrade_config_for_capabilities(sandboxlib_executor):
    '''Simple test of adjusting configuration for a given backend.'''
    in_config = {
        'mounts': 'isolated',
        'network': 'isolated',
        'filesystem_writable_paths': ['/tmp']
    }

    out_config = sandboxlib_executor.degrade_config_for_capabilities(
        in_config, warn=True)

    if sandboxlib_executor == sandboxlib.chroot:
        assert out_config == {
            'mounts': 'undefined',
            'network': 'undefined',
            'filesystem_writable_paths': 'all'
        }
    elif sandboxlib_executor == sandboxlib.linux_user_chroot:
        assert out_config == in_config
