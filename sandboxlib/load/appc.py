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


'''Sandbox loader module for App Container images.'''


import contextlib
import json
import logging
import os
import shutil
import tarfile
import tempfile


# Mandated by https://github.com/appc/spec/blob/master/SPEC.md#execution-environment
BASE_ENVIRONMENT = {
    'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
}


def is_app_container_image(path):
    return path.endswith('.aci')


@contextlib.contextmanager
def unpack_app_container_image(image_file):
    tempdir = tempfile.mkdtemp()
    try:
        # FIXME: you gotta be root, sorry.
        with tarfile.open(image_file, 'r') as tf:
            tf.extractall(path=tempdir)

        manifest_path = os.path.join(tempdir, 'manifest')
        rootfs_path = os.path.join(tempdir, 'rootfs')

        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)

        yield rootfs_path, manifest_data
    finally:
        shutil.rmtree(tempdir)
