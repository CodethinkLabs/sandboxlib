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


'''Unit tests for some utility code.'''


import os
import tempfile
import threading

import sandboxlib



def duplicate_and_assert_data(read_fd, expected_data):
    '''Helper to test the utils.duplicate_streams() method.'''

    with tempfile.TemporaryFile() as f_1:
        with tempfile.TemporaryFile() as f_2:
            sandboxlib.utils.duplicate_streams({read_fd: [f_1, f_2]})
            f_1.seek(0)
            assert f_1.read() == expected_data
            f_2.seek(0)
            assert f_2.read() == expected_data


def write_data_in_thread(write_fd, data):
    '''Helper to test the utils.duplicate_streams() method.

    Since the utils.duplicate_streams() function blocks the main loop until
    all data is transferred, we need to write test data in a separate thread.

    '''
    def write_data(write_fd):
        write_f = os.fdopen(write_fd, 'wb')
        write_f.write(data)
        write_f.close()

    write_thread = threading.Thread(target=write_data, args=[write_fd])
    write_thread.run()


class TestDuplicateStreams(object):
    def test_basic(self):
        '''Write data through a pipe into two files at once.'''

        data = b'Hello\n'
        read_fd, write_fd = os.pipe()
        write_data_in_thread(write_fd, data)
        duplicate_and_assert_data(read_fd, expected_data=data)
        os.close(read_fd)

    def test_binary(self):
        '''Ensure that the code can handle arbitrary binary data.

        It is a common mistake to make to assume data being processed is valid
        UTF-8. POSIX streams don't enforce any kind of character encoding.

        '''

        data = bytearray(range(0,255))
        read_fd, write_fd = os.pipe()
        write_data_in_thread(write_fd, data)
        duplicate_and_assert_data(read_fd, expected_data=data)
        os.close(read_fd)



# Ideas for tests:
#  non-utf8
#  pause without sending EOF.
#  send two streams to one file (stdout and stderr) and ensure ordering is OK.
