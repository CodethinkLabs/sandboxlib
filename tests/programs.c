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


'''Test programs for 'sandboxlib' functional tests.

The tests need to create clean, reproducible sandboxes in order for the tests
to behave the same on all machines. This means not depending on the host OS.
We need some programs to actually run inside the sandbox and try to break them.
There are two approaches: either build / download a small OS from somewhere
that will run in a chroot and will work the same on all platforms, or build
minimal, self-contained tester programs using tools in the host OS.

I picked the second approach: to test the sandboxes using statically linked C
programs. Each C program below should be small, self-contained and should test
one thing.

'''


def build_c_program(source_code, output_path, compiler_args=None):
    '''Compile a temporary C program.'''
    compiler_args = compiler_args or []
    with tempfile.NamedTemporaryFile(suffix='.c') as f:
        f.write(WRITEABLE_PATHS_TEST_CODE.encode('utf-8'))
        f.flush()

        subprocess.check_call(
            ['gcc', '-static', f.name, '-o', str(output_path)])


# Test if a file or directory exists.
FILE_OR_DIRECTORY_EXISTS_TEST_PROGRAM = """
#include <stdio.h>
#include <sys/stat.h>

int main(int argc, char *argv[]) {
    struct stat stat_data;

    if (argc != 2) {
        fprintf(stderr, "Expected 1 argument: filename to try to read from.");
        return 1;
    }

    if (stat(argv[1], &stat_data) != 0) {
        printf("Did not find %s.", argv[1]);
        return 2;
    }

    printf("%s exists", argv[1]);
    return 0;
};
"""

@pytest.fixture(scope='module')
def file_exists_test_program(self, tmpdir):
    program_path = tmpdir.join('writable-paths-tester')
    build_c_program(
        FILE_OR_DIRECTORY_EXISTS_TEST_PROGRAM, program_path, compiler_args=['-static'])
    return program_path

# Test if a file can be written to.
FILE_IS_WRITABLE_TEST_PROGRAM = """
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

@pytest.fixture(scope='module')
def file_is_writable_test_program(self, tmpdir):
    program_path = tmpdir.join('writable-paths-tester')
    build_c_program(
        FILE_IS_WRITEABLE_TEST_PROGRAM, program_path, compiler_args=['-static'])
    return program_path
