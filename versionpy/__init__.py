import glob
import importlib
import os
import shutil
import sys
from os.path import join, isfile, dirname, relpath, isdir
from distutils.version import LooseVersion


COMPONENT_NAMES = {
    0: ['major'],
    1: ['minor'],
    2: ['patch', 'bugfix'],
    3: ['prerelease']
}

def get_component_ind(component_name):
    for k, v in COMPONENT_NAMES.items():
        if component_name.lower() in v:
            return k
    return None


def get_version(pkg, silent=False):
    """
    Used by `version` script
    """
    if not pkg:
        pkg = _find_versioned_package(pkg, silent=silent)
        if not pkg:
            critical(f'Could not find a package with _version.py. Initialize with `bump` if you want to use versionpy.')
    return str(_get_cur_version(pkg, silent=silent))


def increment_version(arg='patch', pkg=None):
    """
    Used by `bump` script
    """
    if pkg and not isdir(pkg):
        log(f'Folder {pkg} does not exist')

    versioned_pkg = _find_versioned_package(pkg)
    if not versioned_pkg:
        if not pkg:
            pkg = _find_folder_to_package()
            if not pkg:
                critical('Could not find a package with _version.py, neither a suitable python package to version')
        log(f'Inititalising {pkg}/_version.py')
    else:
        pkg = versioned_pkg

    version_py = join(pkg, '_version.py')

    if get_component_ind(arg) is not None:  # one of version component names
        if not versioned_pkg:
            new_version = LooseVersion('0.1.0')
            log(f'Initialising with version {new_version}')
        else:
            cur_version = _get_cur_version(pkg)
            if not cur_version:
                critical(f'Cannot parse version from {version_py}')
            components = list(cur_version.version)
            component_ind = get_component_ind(arg)
            log(f'Incrementing {arg} component {components[component_ind]}->{components[component_ind] + 1}')
            components[component_ind] = int(components[component_ind]) + 1

            for lower_component_ind in range(component_ind + 1, len(components)):
                components[lower_component_ind] = 0

            new_version = LooseVersion('.'.join(map(str, components)))

    else:
        new_version = LooseVersion(arg)

    git_rev = get_git_revision()
    with open(version_py, 'w') as f:
        f.write((
            f'# Do not edit this file, pipeline versioning is governed by git tags\n' +
            f'__version__ = \'{new_version}\'\n' +
            f'__git_revision__ = \'{git_rev}\'') + '\n')

    log(f'New version: {new_version}, written to {version_py}')
    return version_py, new_version


def clean_package(package_name, dirpath='.'):
    print('Cleaning up binary, build and dist for ' + package_name + ' in ' + dirpath + '...')
    if isdir(join(dirpath, 'build')):
        shutil.rmtree(join(dirpath, 'build'))
    if isdir(join(dirpath, 'dist')):
        shutil.rmtree(join(dirpath, 'dist'))
    if isdir(join(dirpath, package_name + '.egg-info')):
        shutil.rmtree(join(dirpath, package_name + '.egg-info'))
    print('Done.')


def get_reqs():
    req_fpath = 'requirements.txt'
    if os.path.isfile(req_fpath):
        with open(req_fpath) as f:
            return [l.strip() for l in f.readlines() if not l.startswith('#') and l.strip()]
    return []


def find_package_files(dirpath, package, skip_exts=None):
    paths = []
    for (path, dirs, fnames) in os.walk(join(package, dirpath)):
        for fname in fnames:
            if skip_exts and any(fname.endswith(ext) for ext in skip_exts):
                continue
            fpath = join(path, fname)
            paths.append(relpath(fpath, package))
    return paths


def get_git_revision():
    try:
        import subprocess
        git_revision = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).rstrip()
    except:
        git_revision = ''
        pass
    if isinstance(git_revision, bytes):
        git_revision = git_revision.decode()
    return git_revision


def _get_cur_version(pkg, silent=False):
    """ Tries to find _version.py or VERSION.txt with a value for a current version. On failure, returns None.
    """
    version_py = join(pkg, '_version.py')
    if isfile(version_py):
        ver_str = None
        with open(version_py) as f:
            for l in f:
                if l.startswith('__version__ = '):
                    ver_str = l.split(' = ')[1].strip().strip("'")
                    break
        assert ver_str, f'Cannot read verion from file {version_py}'
        cur_version = LooseVersion(ver_str)
        log(f'Current version as read from {version_py}: {cur_version}', silent=silent)
    else:
        version_txt = 'VERSION.txt'
        if isfile(version_txt):
            cur_version = LooseVersion(open(version_txt).read().strip())
            log(f'Current version as read from {version_txt}: {cur_version}', silent=silent)
        else:
            cur_version = None
    return cur_version


def _find_versioned_package(pkg=None, silent=False):
    found_verpy = glob.glob(f'{pkg or "*"}/_version.py')
    if len(found_verpy) > 1:
        log(f'Found multiple packages containing _version.py: {found_verpy}. If you want to version this project, '
            f'either leave one main package with _verison.py, or specify the target version with -p option')
        sys.exit(1)
    elif len(found_verpy) == 1:
        pkg = dirname(found_verpy[0])
        log(f'Found package with _version.py file: {pkg}', silent=silent)
        return pkg
    else:
        return None


def _find_folder_to_package():
    # TODO: check setup.py for main as well package

    pkg = None
    try:
        import setuptools
        pkgs = setuptools.find_packages()
        if len(pkgs) > 1:
            pkg = input(f'Multiple packages found: {pkgs}. Please specify the main package to version. '
                        f'It will create _version.py file in it and use it to keep track of the version'
                        f'(alternatively, you can rerun with `-p <package_name>`):')
            while not isdir(pkg):
                dirs = [d for d in os.listdir(os.getcwd()) if isdir(d)]
                pkg = input(f'Folder {pkg} does not exist. Available folders: {", ".join(dirs)}')
        elif len(pkgs) == 1:
            pkg = pkgs[0]
    except:
        pass

    if not pkg:
        pkg = input(f'Could not find any packages to version. Please specify folder to initiate _version.py '
                    f'(alternatively, you can rerun with `-p <package_name>`): ')
        while not isdir(pkg):
            dirs = [d for d in os.listdir(os.getcwd()) if isdir(d)]
            pkg = input(f'Folder {pkg} does not exist. Available folders: {", ".join(dirs)}')

    return pkg



def log(msg='', silent=False):
    if not silent:
        sys.stderr.write(msg + '\n')


def critical(msg=''):
    log(msg)
    sys.exit(1)


def click_validate_version(ctx, param, value):
    import click
    if '.' in value:
        comps = value.split('.')
        if len(comps) < 2 or len(comps) > 4:
            raise click.BadParameter(f'Cannot parse version {value}: version must have 2 to 4 components. '
                                     f'Got {len(comps)}')
        for i in range(min(2, len(comps))):
            try:
                int(comps[i])
            except ValueError:
                raise click.BadParameter(f'Cannot parse version {value}: components 1 to 3 must be integer values. '
                                         f'Component {i} is not: {comps[i]}')
    else:
        if get_component_ind(value) is None:
            raise click.BadParameter(
                f'Parameter must be a 2 to 4 component version tag, '
                f'or one of {", ".join(v[-1] for v in COMPONENT_NAMES.values())}')
    return value










