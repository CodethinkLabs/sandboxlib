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


'''Execute command in a sandbox, using 'linux-user-chroot'.

This implements an API defined in sandboxlib/__init__.py.

This backend requires the 'linux-user-chroot' program, which can only be used
with Linux. It also requires the 'unshare' program from the 'util-linux'
package, a 'mount' program that supports the `--make-rprivate` flag, and a 'sh'
program with certain standard features.

The 'linux-user-chroot' program is intended to be 'setuid', and thus usable by
non-'root' users at the discretion of the system administrator. However, the
implementation here also uses 'unshare --mount', which can only be run as
'root'. So this backend can only be run as 'root' at present. Modifying
linux-user-chroot to handle creating the new mount namespace and processing
any extra mounts would be a useful fix.

Supported mounts settings: 'undefined', 'isolated'.

Supported network settings: 'undefined', 'isolated'.

Much of this code is adapted from Morph, from the Baserock project, from code
written by Joe Burmeister, Richard Maw, Lars Wirzenius and others.

'''


import os
import textwrap

import sandboxlib


def maximum_possible_isolation():
    return {
        'mounts': 'isolated',
        'network': 'isolated',
    }


def process_mount_config(root, mounts, extra_mounts):
    # FIXME: currently errors in the generated shell script will appear in the
    # same way as errors from the actual command that the caller wanted to run.
    # That's pretty boneheaded. Could be fixed by setting a flag at the end of
    # the shell script, perhaps.

    supported_values = ['undefined', 'isolated']

    assert mounts in supported_values, \
        "'%s' is an unsupported value for 'mounts' in the " \
        "'linux-user-chroot' backend. Supported values: %s" \
        % (mounts, ', '.join(supported_values))

    # Use 'unshare' to create a new mount namespace.
    #
    # In order to mount the things specified in 'extra_mounts' inside the
    # sandbox's mount namespace, we add a script that runs bunch of 'mount'
    # commands to the 'unshare' commandline. The mounts it creates are
    # unmounted automatically when the namespace is deleted, which is done when
    # 'unshare' exits.
    #
    # The 'undefined' and 'isolated' options are treated the same in this
    # backend, which avoids having a separate, useless code path.

    unshare_command = ['unshare', '--mount', '--', 'sh', '-e', '-c']

    # The single - is just a shell convention to fill $0 when using -c,
    # since ordinarily $0 contains the program name.
    mount_script_args = ['-']

    # This command marks any existing mounts inside the sandboxed filesystem
    # as 'private'. If they were pre-existing 'shared' or 'slave' mounts, it'd
    # be possible to change what is mounted in the sandbox from outside the
    # sandbox, or to change a mountpoint outside the sandbox from within it.
    mount_script = textwrap.dedent(r'''
        mount --make-rprivate /
        root="$1"
        shift
        ''')
    mount_script_args.append(root)

    # The rest of this script processes the items from 'extra_mounts'.
    mount_script += textwrap.dedent(r'''
    while true; do
        case "$1" in
        --)
            shift
            break
            ;;
        *)
            mount_point="$1"
            mount_type="$2"
            mount_source="$3"
            mount_options="$4"
            shift 4
            path="$root/$mount_point"
            mount -t "$mount_type" -o "$mount_options" "$mount_source" "$path"
            ;;
        esac
    done
    ''')

    for source, mount_point, mount_type, mount_options in extra_mounts:
        mount_script_args.extend((mount_point, mount_type, source,
                                  mount_options))
    mount_script_args.append('--')

    mount_script += textwrap.dedent(r'''
    exec "$@"
    ''')

    return unshare_command + [mount_script] + mount_script_args


def process_network_config(network):
    # Network isolation is pretty easy, we 'unshare' the network namespace, and
    # nothing can access the network.

    # Network 'sharing' is a lot harder to tie down: does it just mean 'not
    # blocked'? Or does it mean 'working, with /etc/resolv.conf correctly set
    # up'? So that's not handled yet.

    supported_values = ['undefined', 'isolated']

    assert network in supported_values, \
        "'%s' is an unsupported value for 'network' in the " \
        "'linux-user-chroot' backend. Supported values: %s" \
        % (network, ', '.join(supported_values))

    if network == 'isolated':
        # This is all we need to do for network isolation
        extra_linux_user_chroot_args = ['--unshare-net']
    else:
        extra_linux_user_chroot_args = []

    return extra_linux_user_chroot_args


# This function is mostly taken from Morph, from the Baserock project, from
# file morphlib/fsutils.py.
#
# It is used to convert the whitelist 'filesystem_writable_paths' into a
# blacklist of '--mount-readonly' arguments for linux-user-chroot. It would
# be better if we could pass the whitelist into linux-user-chroot itself,
# all that is needed is a patch to linux-user-chroot.
def invert_paths(tree_walker, paths):
    '''List paths from `tree_walker` that are not in `paths`.

    Given a traversal of a tree and a set of paths separated by os.sep,
    return the files and directories that are not part of the set of
    paths, culling directories that do not need to be recursed into,
    if the traversal supports this.

    `tree_walker` is expected to follow similar behaviour to `os.walk()`.

    This function will remove directores from the ones listed, to avoid
    traversing into these subdirectories, if it doesn't need to.

    As such, if a directory is returned, it is implied that its contents
    are also not in the set of paths.

    If the tree walker does not support culling the traversal this way,
    such as `os.walk(root, topdown=False)`, then the contents will also
    be returned.

    The purpose for this is to list the directories that can be made
    read-only, such that it would leave everything in paths writable.

    Each path in `paths` is expected to begin with the same path as
    yielded by the tree walker.

    '''

    def normpath(path):
        if path == '.':
            return path
        path = os.path.normpath(path)
        if not os.path.isabs(path):
            path = os.path.join('.', path)
        return path
    def any_paths_are_subpath_of(prefix):
        prefix = normpath(prefix)
        norm_paths = (normpath(path) for path in paths)
        return any(path[:len(prefix)] == prefix
                   for path in norm_paths)

    def path_is_listed(path):
        return any(normpath(path) == normpath(other)
                   for other in paths)

    for dirpath, dirnames, filenames in tree_walker:

        if path_is_listed(dirpath):
            # No subpaths need to be considered
            del dirnames[:]
            del filenames[:]
        elif any_paths_are_subpath_of(dirpath):
            # Subpaths may be marked, or may not, need to leave this
            # writable, so don't yield, but we don't cull.
            pass
        else:
            # not listed as a parent or an exact match, needs to be
            # yielded, but we don't need to consider subdirs, so can cull
            yield dirpath
            del dirnames[:]
            del filenames[:]

        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            if path_is_listed(fullpath):
                pass
            else:
                yield fullpath


def process_writable_paths(fs_root, writable_paths):
    if writable_paths == 'all':
        extra_linux_user_chroot_args = []
    else:
        if type(writable_paths) != list:
            assert writable_paths in [None, 'none']
            writable_paths = []

        # FIXME: It's rather annoying that we have to convert the
        # 'writable_paths' whitelist into a blacklist of '--mount-readonly'
        # arguments. It's also possible to break here by making a commandline
        # that is too long, if 'fs_root' contains many directories.

        extra_linux_user_chroot_args = []

        absolute_writable_paths = [
            os.path.join(fs_root, path.lstrip('/')) for path in writable_paths]

        for d in invert_paths(os.walk(fs_root), absolute_writable_paths):
            if not os.path.islink(d):
                rel_path = '/' + os.path.relpath(d, fs_root)
                extra_linux_user_chroot_args.extend(
                    ['--mount-readonly', rel_path])

    return extra_linux_user_chroot_args


def create_mount_points_if_missing(filesystem_root, mount_info_list):
    for source, mount_point, mount_type, mount_options in mount_info_list:
        # Strip the preceeding '/' from mount_point, because it'll break
        # os.path.join().
        mount_point_no_slash = os.path.relpath(mount_point, start='/')

        path = os.path.join(filesystem_root, mount_point_no_slash)
        if not os.path.exists(path):
            os.makedirs(path)


def run_sandbox(command, cwd=None, env=None,
                filesystem_root='/', filesystem_writable_paths='all',
                mounts='undefined', extra_mounts=None,
                network='undefined',
                stdout=sandboxlib.CAPTURE, stderr=sandboxlib.CAPTURE):
    if type(command) == str:
        command = [command]

    linux_user_chroot_command = ['linux-user-chroot']

    extra_mounts = sandboxlib.validate_extra_mounts(extra_mounts)

    unshare_command = process_mount_config(
        root=filesystem_root, mounts=mounts, extra_mounts=extra_mounts or [])

    linux_user_chroot_command += process_network_config(network)

    if cwd is not None:
        linux_user_chroot_command.extend(['--chdir', cwd])

    linux_user_chroot_command += process_writable_paths(
        filesystem_root, filesystem_writable_paths)

    linux_user_chroot_command.append(filesystem_root)

    create_mount_points_if_missing(filesystem_root, extra_mounts)

    argv = (unshare_command + linux_user_chroot_command + command)
    exit, out, err = sandboxlib._run_command(argv, stdout, stderr, env=env)
    return exit, out, err


def run_sandbox_with_redirection(command, **sandbox_config):
    exit, out, err = run_sandbox(command, **sandbox_config)
    # out and err will be None
    return exit
