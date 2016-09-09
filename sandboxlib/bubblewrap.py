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

"""Execute command in a sandbox, using 'bubblewrap'.

This implements an API defined in sandboxlib/__init__.py.
"""


import os
import logging
import logging.config
import sandboxlib

bwrap_abspath=os.path.dirname(__file__)
logging.config.fileConfig(os.path.join(bwrap_abspath, 'logger.conf'))

log = logging.getLogger("sandboxlib")
# FIXME copied over from `linux_user_chroot`, not sure on what is expected here.
CAPABILITIES = {
    'network': ['isolated', 'undefined'],
    'mounts': ['isolated', 'undefined'],
    'filesystem_writable_paths': ['all', 'any'],
}


def degrade_config_for_capabilities(in_config, warn=True):
    # This backend has the most features, right now!
    log.debug("Nothing to degrade in bwrap config")
    return in_config


def run_sandbox(command, cwd=None, env=None,
                filesystem_root='/', filesystem_writable_paths='all',
                mounts='undefined', extra_mounts=None,
                network='undefined',
                stderr=sandboxlib.CAPTURE, stdout=sandboxlib.CAPTURE):
    """Run 'command' in a sandboxed environment.

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

    """

    log.debug("cmd: {}, cwd: {}, env: {}, filesystem_root: {}, "
              "filesystem_writable_paths: {}, mounts: {}, extra_mounts: {}, "
              "network: {}, stderr: {}, stdout: {}".format(
                command, cwd, env, filesystem_root, filesystem_writable_paths,
                mounts, extra_mounts, network, stderr, stdout))
    
    if type(command) == str:
        command = [command]

    # Bwrap full path
    bwrap_command = [bubblewrap_program()]
    log.debug("/path/to/bwrap : {}".format(bwrap_command))

    # Add in the root filesystem stuff first
    # rootfs is mounted as RW initially so that further mounts can be placed on top
    # If a RO root is required, after all other mounts are complete, root is
    # remounted as RO
    bwrap_command += ["--bind", filesystem_root, "/"]

    bwrap_command += process_network_config(network)
 
    if cwd is not None:
        log.debug("Setting cwd to '{}'".format(cwd))
        bwrap_command.extend(['--chdir', cwd])
 
    # do pre checks on mounts
    extra_mounts = sandboxlib.validate_extra_mounts(extra_mounts)
    create_mount_points_if_missing(filesystem_root, extra_mounts)

    # Handles the ro and rw mounts
    bwrap_command += process_mounts(filesystem_root, extra_mounts,
                                    filesystem_writable_paths)



    argv = bwrap_command + command
    log.info("bubblewrap.run_command({}, stdou:{}, stderr:{}, env:{})"
             .format(" ".join(argv), stdout, stderr, env))
    
    exit, out, err = sandboxlib._run_command(argv, stdout, stderr, env=env)
    
    return exit, out, err


def run_sandbox_with_redirection(command, **sandbox_config):
    """Start a subprocess in a sandbox, redirecting stderr and/or stdout.

    The sandbox_config arguments are the same as the run_command() function.

    This returns just the exit code, because if stdout or stderr are redirected
    those values will be None in any case.

    """

    exit, out, err = run_sandbox(command, **sandbox_config)
    # out and err will be None
    return exit

# Non API methods below


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
            log.debug("making empty '{}' directory in '{}'".
                      format(mount_point_no_slash, filesystem_root))

            os.makedirs(path)


def process_network_config(network):
    sandboxlib.utils.check_parameter('network', network, CAPABILITIES['network'])

    if network == 'isolated':
        # This is all we need to do for network isolation
        network_args = ['--unshare-net']
    else:
        network_args = []

    return network_args


def process_mounts(fs_root, mounts, writable_paths):
    """
    filesystem_writable_paths: defaults to 'all', which allows the command
            to write to anywhere under 'filesystem_root' that the user of the
            calling process could write to. Backends may accept a list of paths
            instead of 'all', and will prevent writes to any files not under a
            path in that whitelist. If 'none' or an empty list is passed, the
            whole file-system will be read-only. The paths should be relative
            to filesystem_root. This will processed /after/ extra_mounts are
            mounted.
    extra_mounts: a list of locations to mount inside 'rootfs_path',
            specified as a list of tuples of (source_path, target_path, type,
            options). The 'type' and 'options' should match what would be
            specified in /etc/fstab, but a backends may support only a limited
            subset of values. The 'target_path' is relative to filesystem_root
            and will be created before mounting if it doesn't exist.
    """

    log.debug("process_mounts(fs_root={}, mounts={}, writable_paths={})".format(fs_root, mounts, writable_paths))
    extra_args = []
    fs_dict = {}
    
    for ex_mnt in mounts:
        mnt_src, mnt_target, mnt_type, mnt_options = ex_mnt
        # TODO
        # How to handle options? Can bwrap do this?
        
        if mnt_target not in fs_dict.keys():
            fs_dict[mnt_target] = {'src': mnt_src, 'type': mnt_type, 'options': mnt_options}
        # already exists. should only upgrade some things
        else:
            # Use current files/folders from host
            if fs_dict[mnt_target]['type'] == "tmpfs"\
                    and is_mount_writable(mnt_target, writable_paths):
                fs_dict[mnt_target]['type'] = None
                fs_dict[mnt_target]['src'] = mnt_src
            # else ??

    # This needs to be done to turn tmpfs mounts into normal binded mounts
    # when we are expecting data to already be inside the mount, else an
    # empty mount is made. This breaks the test_mount_point_writable test
    if type(writable_paths) is list:
        for wr_mnt in writable_paths:
            if wr_mnt not in fs_dict.keys():
                fs_dict[wr_mnt] = {}

            # fs_dict[wr_mnt]['options'] = None
            # fs_dict[wr_mnt]['type'] = None
            fs_dict[wr_mnt]['src'] = os.path.join(fs_root, wr_mnt.strip("/"))

    for k, v in fs_dict.items():
        mnt_src = v['src']
        mnt_target = k
        mnt_type = v.get('type', None)
        mnt_options = v.get('options', None)

        log.debug("mount ({},{},{},{})".format(mnt_src, mnt_target, mnt_type, mnt_options))

        if mnt_options is "bind":
            # For legacy reasons, 'bind' is set as an option for some reason, instead
            # of listed in filesystem_writable_paths. We will append the path here anyway
            writable_paths.append(mnt_target)

        if mnt_type == "proc":
            extra_args.extend(['--proc', mnt_target])
        elif mnt_type == "tmpfs":
            extra_args.extend(['--tmpfs', mnt_target])
        elif mnt_target == "/dev":
            # TODO dev can be mounted in two ways in bwrap
            # First is using the --dev option that mounts host /dev
            # Second is using --dev-bind for moutning a [src] to [dest]
            # while allowing device access.
            #
            # How do we diferentiate the two?

            # extra_args.extend(['--dev', mnt_target])

            # Experiment to see if --dev-bind fixes permissions errors
            log.info("Using --dev-bind instead")
            extra_args.extend(['--dev-bind', mnt_src, mnt_target])
        else:
            if is_mount_writable(mnt_target, writable_paths):
                extra_args.extend(['--bind', mnt_src, mnt_target])
            else:
                extra_args.extend(['--ro-bind', mnt_src, mnt_target])

    # Final remount if root is read-only
    if not is_mount_writable("/", writable_paths):
        log.debug("/ is set as RO")
        extra_args += ["--remount-ro", "/"]

    return extra_args

                
def is_mount_writable(mnt, writable_paths):
    # Deal with the catch all statements first
    if writable_paths == 'all':
        return True
    elif writable_paths in ['none', []]:
        return False
    elif type(writable_paths) is list:
        return mnt in writable_paths
        
    # Default/unknown case
    else:
        log.warn("Unknown bubblewrap.writable_path arg type given : {} type({})"
                 .format(writable_paths, type(writable_paths)))
        
        return False
