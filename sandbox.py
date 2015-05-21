# Make a sandbox for running a command.

# Sandbox could be: a baserock chroot, for the time being.

# Image layout: /rootfs, /manifest


import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile


def appc_manifest_for_command(command):
    '''Fake an appc manifest.'''
    manifest = {
        'acKind': 'ImageManifest',
        'acVersion': '0.5.2',
        'name': 'temp/temp1',
        'labels': [],
        'app': {
            'exec': command,
            'user': 'root',
            'group': 'root',
            'workingDirectory': '/temp.build',
        }
    }
    return json.dumps(manifest)

def make_sandbox_for_command(command, source_tar, target,
                             actool='/home/shared/baserock/appc-spec/actool/actool'):
    '''Fake an appc image.

    This is a dumb idea, because you have to unpack a tar, create a tar, then
    unpack it again to run it.

    Better to have the executor take manifest and rootfs separately.

    '''
    tempdir = tempfile.mkdtemp()

    try:
        manifest_path = os.path.join(tempdir, 'manifest')
        rootfs_path = os.path.join(tempdir, 'rootfs')

        with open(manifest_path, 'w') as f:
            f.write(appc_manifest_for_command(command))

        os.mkdir(rootfs_path)
        # FIXME: You've probably got to run this as root.
        with tarfile.TarFile(source_tar, 'r') as tf:
            tf.extractall(path=rootfs_path)

        subprocess.check_call(
            [actool, 'build', tempdir, target],
            stdout=sys.stdout,
            stderr=sys.stderr)
        print 'Created %s' % target
    finally:
        shutil.rmtree(tempdir)


make_sandbox_for_command(
    command=['/bin/sh', '-c', '"echo foo && exit 1"'],
    source_tar='/home/shared/baserock-chroot-src/definitions/baserock-minimal.tar',
    target='/home/shared/baserock/baserock-minimal.aci')
