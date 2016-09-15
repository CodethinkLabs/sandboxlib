# Copyright (C) 2016  Codethink Limited
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

'''Execute command in a sandbox, using 'bubblewrap'.

This implements an API defined in sandboxlib/__init__.py.

'''


import os
import logging

import sandboxlib

#FIXME copied over from `linux_user_chroot`, not sure on what is expected here.
CAPABILITIES = {
    'network': ['isolated', 'undefined'],
    'mounts': ['isolated', 'undefined'],
    'filesystem_writable_paths': ['all', 'any'],
}

def degrade_config_for_capabilities(in_config, warn=True):
    # This backend has the most features, right now!
    return in_config

def run_sandbox(command, cwd=None, env=None,
                filesystem_root='/', filesystem_writable_paths='all',
                mounts='undefined', extra_mounts=None,
                network='undefined',
                stderr=sandboxlib.CAPTURE, stdout=sandboxlib.CAPTURE):
    '''Run 'command' in a sandboxed environment.

    Parameters:
      - command: the command to run. Pass a list of parameters rather than
            using spaces to separate them, e.g. ['echo', '"Hello world"'].
      - cwd: the working directory of 'command', relative to 'rootfs_path'.
            Defaults to '/' if "rootfs_path" is specified, and the current
            directory of the calling process otherwise.
      - env: environment variables to set
      - filesystem_root: the path to the root of the sandbox. Defaults to '/',
            which doesn't isolate the command from the host filesystem at all.
      - filesystem_writable_paths: defaults to 'all', which allows the command
            to write to anywhere under 'filesystem_root' that the user of the
            calling process could write to. Backends may accept a list of paths
            instead of 'all', and will prevent writes to any files not under a
            path in that whitelist. If 'none' or an empty list is passed, the
            whole file-system will be read-only. The paths should be relative
            to filesystem_root. This will processed /after/ extra_mounts are
            mounted.
      - mounts: configures mount sharing. Defaults to 'undefined', where no
            no attempt is made to isolate mounts. Backends may support
            'isolated' as well.
      - extra_mounts: a list of locations to mount inside 'rootfs_path',
            specified as a list of tuples of (source_path, target_path, type,
            options). The 'type' and 'options' should match what would be
            specified in /etc/fstab, but a backends may support only a limited
            subset of values. The 'target_path' is relative to filesystem_root
            and will be created before mounting if it doesn't exist.
      - network: configures network sharing. Defaults to 'undefined', where
            no attempt is made to either prevent or provide networking
            inside the sandbox. Backends may support 'isolated' and/or other
            values as well.
      - stdout: whether to capture stdout, or redirect stdout to a file handle.
            If set to sandboxlib.CAPTURE, the function will return the stdout
            data, if not, it will return None for that. If stdout=None, the
            data will be discarded -- it will NOT inherit the parent process's
            stdout, unlike with subprocess.Popen(). Set 'stdout=sys.stdout' if
            you want that.
      - stderr: same as stdout

    Returns:
      a tuple of (exit code, stdout output, stderr output).

    '''
    
    log = logging.getLogger("sandboxlib")
    log.warn("In sandbox fn, args")
    log.warn("cmd: {}, cwd: {}, env: {}, filesystem_root: {}," \
             "filesystem_writable_paths: {}, mounts: {}, extra_mounts: {}, "\
             "network: {}, stderr: {}, stdout: {}".format(
                command, cwd, env, filesystem_root, filesystem_writable_paths,
                mounts, extra_mounts, network, stderr, stdout))
    
    if type(command) == str:
        command = [command]

    bwrap_command = [bubblewrap_program()]
    log.warn("bwrap cmd : {}".format(bwrap_command))
    
    extra_mounts = sandboxlib.validate_extra_mounts(extra_mounts)
    
    bwrap_command += process_network_config(network)
 
    if cwd is not None:
        bwrap_command.extend(['--chdir', cwd])
    log.warn(bwrap_command)
 
    #create_mount_points_if_missing(filesystem_root, filesystem_writable_paths)
    for w_mnt in filesystem_writable_paths:
        bwrap_command.extend(['--bind', w_mnt])
 
    create_mount_points_if_missing(filesystem_root, extra_mounts)
    for ex_mnt in extra_mounts:
        bwrap_command.extend(['--ro-bind', ex_mnt])
    
    log.warn(bwrap_command)
    argv = bwrap_command + [filesystem_root] + command
    print("run_command({}, {}, {}, {})"
             .format(argv, stdout, stderr, env))
    exit, out, err = sandboxlib._run_command(argv, stdout, stderr, env=env)
    
    return exit, out, err

def run_sandbox_with_redirection(command, **sandbox_config):
    '''Start a subprocess in a sandbox, redirecting stderr and/or stdout.

    The sandbox_config arguments are the same as the run_command() function.

    This returns just the exit code, because if stdout or stderr are redirected
    those values will be None in any case.

    '''
    exit, out, err = run_sandbox(command, **sandbox_config)
    # out and err will be None
    return exit

## Non API methods below

def bubblewrap_program():
    # Raises sandboxlib.ProgramNotFound if not found.
    return sandboxlib.utils.find_program('bwrap')

def create_mount_points_if_missing(filesystem_root, mount_info_list):
    for source, mount_point, mount_type, mount_options in mount_info_list:
        # Strip the preceeding '/' from mount_point, because it'll break
        # os.path.join().
        mount_point_no_slash = os.path.abspath(mount_point).lstrip('/')

        path = os.path.join(filesystem_root, mount_point_no_slash)
        if not os.path.exists(path):
            os.makedirs(path)
            
def process_network_config(network):

    sandboxlib.utils.check_parameter('network', network, CAPABILITIES['network'])

    if network == 'isolated':
        # This is all we need to do for network isolation
        network_args = ['--unshare-net']
    else:
        network_args = []

    return network_args