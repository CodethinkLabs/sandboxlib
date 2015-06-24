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


def test_duplicate_streams():
    read_fd, write_fd = os.pipe()

    def write_data(write_fd):
        write_f = os.fdopen(write_fd, 'wb')
        write_f.write('hello\n'.encode('utf-8'))
        write_f.close()

    write_thread = threading.Thread(target=write_data, args=[write_fd])
    write_thread.run()

    #os.close(write_fd)

    with tempfile.TemporaryFile() as f_1:
        with tempfile.TemporaryFile() as f_2:
            sandboxlib.utils.duplicate_streams({read_fd: [f_1, f_2]})
            f_1.seek(0)
            assert f_1.read().decode('utf-8') == 'hello\n'
            f_2.seek(0)
            assert f_2.read().decode('utf-8') == 'hello\n'
