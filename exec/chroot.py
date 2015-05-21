# Run a sandbox in a chroot.


import contextlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile


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


def _run_sandbox_real(rootfs_path, manifest, command=None):
    # FIXME: you gotta be root.
    print manifest
    if command is None:
        # Use the command from the image
        command = manifest['app']['exec']
    if type(command) == str:
        command = [command]
    subprocess.call(['chroot', rootfs_path] + command)


def run_sandbox(app_container_image=None,
                rootfs_path=None,
                manifest=None,
                command=None):
    if app_container_image is not None:
        assert rootfs_path is None and manifest is None, \
            "You cannot specify a rootfs_path or manifest when running an " \
            "App Container image."
        with unpack_app_container_image(app_container_image) as (rootfs_path, manifest):
            return _run_sandbox_real(rootfs_path, manifest, command=command)
    else:
        _run_sandbox_real(rootfs_path, manifest, command=command)


run_sandbox(app_container_image='/home/shared/baserock/baserock-minimal.aci',
            command=['/bin/sh', '-c', 'echo foo && exit 1'])
