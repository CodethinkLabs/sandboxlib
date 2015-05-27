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
import subprocess
import tempfile

import sandboxlib


def build_c_program(source_code, output_path, compiler_args=None):
    '''Compile a temporary C program.

    In order that the test suite be self-contained, we test the sandboxes
    using statically linked C programs. The alternative would be to depend on
    some operating system image that can run in a container.

    '''
    compiler_args = compiler_args or []
    with tempfile.NamedTemporaryFile(suffix='.c') as f:
        f.write(WRITEABLE_PATHS_TEST_CODE.encode('utf-8'))
        f.flush()

        subprocess.check_call(
            ['gcc', '-static', f.name, '-o', str(output_path)])


@pytest.fixture(params=['chroot', 'linux_user_chroot'])
def sandboxlib_executor(request):
    executor = getattr(sandboxlib, request.param)

    if request.param == 'chroot' and os.getuid() != 0:
        pytest.skip('chroot backend can only be used by root users')

    return executor


def test_stdout(sandboxlib_executor):
    exit, out, err = sandboxlib_executor.run_sandbox(['echo', 'xyzzy'])

    assert exit == 0
    assert out.decode('unicode-escape') == 'xyzzy\n'
    assert err.decode('unicode-escape') == ''


def test_current_working_directory(sandboxlib_executor, tmpdir):
    exit, out, err = sandboxlib_executor.run_sandbox(
        ['pwd'], cwd=str(tmpdir))

    assert exit == 0
    assert out.decode('unicode-escape') == '%s\n' % str(tmpdir)
    assert err.decode('unicode-escape') == ''


def test_mounts(sandboxlib_executor, tmpdir):
    # FIXME: This test will fail because we try to run a command in an empty
    # chroot. Need some kind of statically linked C program to run in there.
    exit, out, err = sandboxlib_executor.run_sandbox(
        ['/bin/ls', '/proc'],
        filesystem_root=str(tmpdir),
        extra_mounts=[(None, '/proc', 'proc')])


# The simplest way to test these sandboxes is with a statically linked C
# program.
WRITEABLE_PATHS_TEST_CODE = """
#include <stdio.h>

int main(int argc, char *argv[]) {
    FILE *file;

    if (argc != 2) {
        fprintf(stderr, "Expected 1 argument: filename to try to write to.");
        return 1;
    }

    file = fopen(argv[0], "w");

    if (file == NULL) {
        printf("Couldn't open %s for writing.", argv[1]);
        return 2;
    }

    if (fputc('!', file) != '!') {
        printf("Couldn't write to %s.", argv[1]);
        fclose(file);
        return 3;
    }

    fclose(file);
    printf("Wrote data to %s.", argv[1]);
    return 0;
};
"""


class TestWriteablePaths(object):
    @pytest.fixture(scope='module')
    def writable_paths_test_program(self, tmpdir):
        program_path = tmpdir.join('writable-paths-tester')
        build_c_program(
            WRITEABLE_PATHS_TEST_CODE, program_path, compiler_args=['-static'])
        return program_path

    @pytest.fixture()
    def writable_paths_test_sandbox(self, tmpdir, writable_paths_test_program):
        sandbox_path = tmpdir.mkdir('sandbox')

        bin_path = sandbox_path.mkdir('bin')

        writable_paths_test_program.copy(bin_path)
        bin_path.join('writable-paths-tester').chmod(0o755)

        data_path = sandbox_path.mkdir('data')
        data_path.mkdir('1')
        data_path.join('canary').write("Please don't overwrite me.")

        return sandbox_path

    def test_none_writable(self, sandboxlib_executor,
                            writable_paths_test_sandbox):
        if sandboxlib_executor == sandboxlib.chroot:
            pytest.xfail("chroot backend doesn't support read-only paths.")

        exit, out, err = sandboxlib_executor.run_sandbox(
            ['writable-paths-tester', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths='none')

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Couldn't open /data/1/canary for writing."
        assert exit == 2

    def test_some_writable(self, sandboxlib_executor,
                           writable_paths_test_sandbox):
        if sandboxlib_executor == sandboxlib.chroot:
            pytest.xfail("chroot backend doesn't support read-only paths.")

        exit, out, err = sandboxlib_executor.run_sandbox(
            ['writable-paths-tester', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths=['/data/1'])

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Wrote data to /data/1/canary."
        assert exit == 0

    def test_all_writable(self, sandboxlib_executor,
                          writable_paths_test_sandbox):
        exit, out, err = sandboxlib_executor.run_sandbox(
            ['writable-paths-tester', '/data/1/canary'],
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
            ['writable-paths-tester', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths='none',
            extra_mounts=[
                (None, '/data', 'tmpfs')
            ])

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Couldn't open /data/1/canary for writing."
        assert exit == 2

    def test_mount_point_writable(self, sandboxlib_executor,
                                  writable_paths_test_sandbox):
        if sandboxlib_executor == sandboxlib.chroot:
            pytest.xfail("chroot backend doesn't support read-only paths.")

        exit, out, err = sandboxlib_executor.run_sandbox(
            ['writable-paths-tester', '/data/1/canary'],
            filesystem_root=str(writable_paths_test_sandbox),
            filesystem_writable_paths=['/data'],
            extra_mounts=[
                (None, '/data', 'tmpfs')
            ])

        assert err.decode('unicode-escape') == ''
        assert out.decode('unicode-escape') == \
            "Wrote data to /data/1/canary."
        assert exit == 0
