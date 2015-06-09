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
