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


import asynchat
import asyncore
import logging
import os
import shutil
import subprocess
import sys

import sandboxlib


def check_parameter(name, value, supported_values):
    assert value in supported_values, \
        "'%(value)s' is an unsupported value for '%(name)s' in this " \
        "backend. Supported values: %(supported_values)s".format(
            name=name, value=value,
            supported_values=', '.join(supported_values))


def find_program(program_name):
    search_path = os.environ.get('PATH')

    # Python 3.3 and newer provide a 'find program in PATH' function. Otherwise
    # we fall back to the `which` program.
    if sys.version_info.major >= 3 and sys.version_info.minor >= 3:
        program_path = shutil.which(program_name, path=search_path)
    else:
        try:
            argv = ['which', program_name]
            program_path = subprocess.check_output(argv).strip()
        except subprocess.CalledProcessError as e:
            logging.debug("Error searching for %s: %s", program_name, e)
            program_path = None

    if program_path is None:
        raise sandboxlib.ProgramNotFound(
            "Did not find '%s' in PATH. Searched '%s'" % (
                program_name, search_path))

    return program_path


class AsyncoreFileWrapperWithEOFHandler(asyncore.file_wrapper):
    '''File wrapper that reports when it hits the end-of-file marker.

    The asyncore.file_wrapper class wraps a file in a way that makes it
    act like a socket, so that it can easily be used in an 'asyncore' main
    loop. We use this with the asynchat.async_chat class, which provides a
    channel that parses the output of a stream and calls a callback function.
    The one hitch is that asynchat.async_chat doesn't notice when the stream
    has hit the end-of-file delimeter. This class is a workaround which causes
    the AsyncoreStreamProcessingChannel instance to close itself once the end
    of the stream is reached.

    '''
    def __init__(self, dispatcher, fd):
        self._dispatcher = dispatcher
        asyncore.file_wrapper.__init__(self, fd)

    def recv(self, *args):
        data = asyncore.file_wrapper.recv(self, *args)
        if not data:
            self._dispatcher.close_when_done()
            # ensure any unterminated data is flushed
            return self._dispatcher.get_terminator()
        return data


class AsyncoreStreamProcessingChannel(asynchat.async_chat,
                                      asyncore.file_dispatcher):
    '''Channel to read from a stream and pass the data to a handler function.

    The 'asyncore' module provides a select()-based main loop. We use this in
    duplicate_streams() to multiplex reading from various streams and
    duplicating their output. This class provides a channel that can be added
    the 'asyncore' main loop and will read from a given file descriptor, and
    call a given callback function at the end of each line.

    '''
    def __init__(self, fd, line_handler, map=None):
        asynchat.async_chat.__init__(self, sock=None, map=map)
        asyncore.file_dispatcher.__init__(self, fd=fd, map=map)
        self.set_terminator(b'\n')
        self._line_handler = line_handler

    class FileWrapperWithEOFHandler(asyncore.file_wrapper):
        '''File wrapper that reports when it hits the end-of-file marker.

        The asyncore.file_wrapper class makes a stream object behave like a
        socket object, so it can be managed by the asyncore.dispatcher code.
        This subclass is a workaround for the fact that the asynchat.async_chat
        class doesn't handle the end-of-file delimiter, so we need to hook into
        the recv() method and manually close the channel when we see EOF.

        '''
        def __init__(self, dispatcher, fd):
            self._dispatcher = dispatcher
            asyncore.file_wrapper.__init__(self, fd)

        def recv(self, *args):
            data = asyncore.file_wrapper.recv(self, *args)
            if not data:
                self._dispatcher.close_when_done()
                # ensure any unterminated data is flushed
                return self._dispatcher.get_terminator()
            return data

    collect_incoming_data = asynchat.async_chat._collect_incoming_data

    def set_file(self, fd):
        # Called on initialisation.
        self.socket = AsyncoreFileWrapperWithEOFHandler(self, fd)
        self._fileno = self.socket.fileno()
        self.add_channel()

    def found_terminator(self):
        # Called when the \n terminator is found in the input data.
        for data in self.incoming:
            self._line_handler(b''.join(self.incoming) + self.terminator)
        self.incoming = []


def duplicate_streams(stream_map, flush_interval=0.0):
    '''Copy data from one or more input streams to multiple output streams.

    Similar to the `tee` commandline utility, this can be used for echoing
    'stdout' and 'stderr' of a subprocess to the parent's 'stdout' and
    'stderr', whilst also saving it all to a log file.

    This function will block until the end-of-file terminator has been received
    on all of the input streams.

    '''
    # The AsyncoreStreamProcessingChannel instances are tracked in socket_map.
    socket_map = {}

    for input_fd, output_fds in stream_map.items():
        def write_line(line):
            for fd in output_fds:
                fd.write(line)

        AsyncoreStreamProcessingChannel(
            line_handler=write_line, fd=input_fd, map=socket_map)

    while socket_map:
        asyncore.loop(timeout=flush_interval, use_poll=True, map=socket_map,
                      count=1)
        print(socket_map)
