import json
import logging
from pathlib import Path
from functools import wraps
from operator import methodcaller
from textwrap import indent, dedent
from collections import defaultdict


# from dask import delayed
from toposort import toposort
from dockermap.api import DockerFile, DockerClientWrapper
from dockermap.shortcuts import mkdir
from dockermap.build.dockerfile import format_command


logger = logging.getLogger(__name__)


class DockerFile(DockerFile):

    def __str__(self):
        return self.fileobj.getvalue().decode('utf-8')


class DockerImage:

    def __init__(self, name, base, tag='latest', org='ursalab', arch=None,
                 os=None, variant=None, steps=tuple()):
        if isinstance(base, DockerImage):
            if os is not None and os != base.os:
                raise ValueError(
                    f"Given os `{os}` is not equal with the base "
                    f"image's os `{base.os}`"
                )
            if arch is not None and arch != base.arch:
                raise ValueError(
                    f"Given architecture `{arch}` is not equal with the base "
                    f"image's architecture `{base.arch}`"
                )
            os, arch, variant = base.os, base.arch, base.variant
        elif not isinstance(base, str):
            raise TypeError(
                '`tag` argument must be an instance of DockerImage or str'
            )

        if not isinstance(name, str):
            raise TypeError(f'`name` argument must be an instance of str')
        if not isinstance(org, str):
            raise TypeError(f'`org` argument must be an instance of str')
        if not isinstance(tag, str):
            raise TypeError(f'`tag` argument must be an instance of str')
        if not isinstance(os, str):
            raise TypeError(f'`os` argument must be an instance of str')
        if variant is not None and not isinstance(variant, str):
            raise TypeError(f'`variant` argument must be an instance of str')

        if arch not in {'amd64', 'arm64v8'}:
            raise ValueError(f'invalid architecture `{arch}`')

        if not isinstance(steps, (tuple, list)):
            raise TypeError(
                '`steps` argument must be an instance of list or tuple'
            )
        elif not all(callable(step) for step in steps):
            raise TypeError(
                'each `step` must be a callable, use `run` function'
            )

        self.name = name
        self.base = base
        self.org = org
        self.tag = tag
        self.arch = arch
        self.os = os
        self.variant = variant
        self.steps = steps

    def __str__(self):
        return self.fqn

    def __repr__(self):
        return f'<DockerImage: {self.repo}:{self.tag} at {id(self)}>'

    def __hash__(self):
        return hash(self.fqn)

    @property
    def fqn(self):
        return f'{self.org}/{self.repo}:{self.tag}'

    @property
    def repo(self):
        repo = f'{self.arch}-{self.os}'
        if self.variant is not None:
            repo += f'-{self.variant}'
        return repo + f'-{self.name}'

    @property
    def platform(self):
        return (self.arch, self.os, self.variant)

    @property
    def dockerfile(self):
        # self.base is either a string or a DockerImage instance
        df = DockerFile(str(self.base))
        for callback in self.steps:
            callback(df)
        df.finalize()
        return df

    def save_dockerfile(self, directory):
        path = Path(directory) / f'{self.repo}.{self.tag}.dockerfile'
        self.dockerfile.save(path)

    def build(self, client=None, **kwargs):
        if client is None:
            client = DockerClientWrapper()

        # wrap it in a try catch and serialize the failing dockerfile
        # also consider to use add an `org` argument to directly tag the image
        # TODO(kszucs): pass platform argument
        logger.info(f'Start building {self.fqn}')
        client.build_from_file(self.dockerfile, self.fqn, **kwargs)
        logger.info(f'Image is build successfully: {self.fqn}')

        return self

    def push(self, client=None, **kwargs):
        if client is None:
            client = DockerClientWrapper()

        client.push(self.fqn, **kwargs)
        return self


class ImageCollection(list):

    def build(self, *args, **kwargs):
        deps = defaultdict(set)
        for image in self:
            # image.base is either a string or a DockerImage, in the former
            # case it is going to be pulled from the registry instead of
            # being built by us
            if isinstance(image.base, DockerImage):
                deps[image].add(image.base)

        for image_set in toposort(deps):
            for image in image_set:
                image.build(*args, **kwargs)

    def push(self, *args, **kwargs):
        # topological sort is not required because the layers are cached
        for image in self:
            image.push(*args, **kwargs)

    def filter(self, **kwargs):
        imgs = self
        for by, value in kwargs.items():
            imgs = filter(lambda item: getattr(item, by) == value, imgs)
        return ImageCollection(imgs)


# functions to define dockerfiles from python


_tab = ' ' * 4


@wraps(DockerFile.add_file, ('__doc__',))
def ADD(*args, **kwargs):
    return methodcaller('add_file', *args, **kwargs)


@wraps(DockerFile.run, ('__doc__',))
def RUN(*args):
    return methodcaller('run', *args)


def ENV(**kwargs):
    args = tuple(map("=".join, kwargs.items()))
    args = indent(" \\\n".join(args), _tab).lstrip()
    return methodcaller('prefix', 'ENV', args)


def WORKDIR(workdir):
    return lambda df: setattr(df, 'command_workdir', workdir)


def USER(username):
    return lambda df: setattr(df, 'command_user', username)


def _command(prefix, cmd):
    assert isinstance(cmd, (str, list, tuple))
    is_shell = isinstance(cmd, str)

    # required because a bug in dockermap/build/dockerfile.py#L77
    if not is_shell and isinstance(cmd, (list, tuple)):
        cmd = json.dumps(list(map(str, cmd)))
    else:
        cmd = format_command(cmd, is_shell)

    return methodcaller('prefix', prefix, cmd)


def CMD(cmd):
    return _command('CMD', cmd)


def ENTRYPOINT(entrypoint):
    return _command('ENTRYPOINT', entrypoint)


def SHELL(shell):
    return _command('SHELL', shell)


# command shortcuts


def apt(*packages):
    """Generates apt install command"""
    template = dedent("""
        apt update -y -q && \\
        apt install -y -q \\
        {} && \\
        rm -rf /var/lib/apt/lists/*
    """)
    args = indent(' \\\n'.join(packages), _tab)
    cmd = indent(template.format(args), _tab)
    return cmd.lstrip()


def apk(*packages):
    """Generates apk install command"""
    template = dedent("""
        apk add --no-cache -q \\
        {}
    """)
    args = indent(' \\\n'.join(packages), _tab)
    cmd = indent(template.format(args), _tab)
    return cmd.lstrip()


def pip(*packages, files=tuple()):
    """Generates pip install command"""
    template = dedent("""
        pip install \\
        {}
    """)
    args = tuple(f'-r {f}' for f in files) + packages
    args = indent(' \\\n'.join(args), _tab)
    cmd = indent(template.format(args), _tab)
    return cmd.lstrip()


def conda(*packages, files=tuple()):
    """Generate conda install command"""
    template = dedent("""
        conda install -y -q \\
        {} && \\
        conda clean -q --all
    """)
    args = tuple(f'--file {f}' for f in files) + packages
    args = indent(' \\\n'.join(args), _tab)
    cmd = indent(template.format(args), _tab)
    return cmd.lstrip()


images = ImageCollection()
docker = Path(__file__).parent.parent / 'docker'


ubuntu_pkgs = [
    'autoconf',
    'build-essential',
    'cmake',
    'libboost-dev',
    'libboost-filesystem-dev',
    'libboost-regex-dev',
    'libboost-system-dev',
    'python',
    'python-pip',
    'bison',
    'flex',
    'git',
    # zstd ep requires CMake >= 3.7 which is not available for ubuntu 16.04
    'libzstd1-dev',
    'ninja-build'
]

alpine_pkgs = [
    'autoconf',
    'bash',
    'bison',
    'boost-dev',
    'cmake',
    'flex',
    'g++',
    'gcc',
    'git',
    'gzip',
    'make',
    'musl-dev',
    'ninja',
    'wget',
    'zlib-dev',
    'python-dev'
]

# TODO(kszucs): add buildbot user
worker_command = 'twistd --pidfile= -ny buildbot.tac'
worker_steps = [
    RUN(pip('buildbot-worker')),
    RUN(mkdir('/buildbot')),
    ADD(docker / 'buildbot.tac', '/buildbot/buildbot.tac'),
    WORKDIR('/buildbot'),
    CMD(worker_command)  # not this is string!
]
conda_worker_steps = (
    [RUN(conda('twisted'))] +
    worker_steps +
    [CMD([worker_command])]  # note this is list!
)

python_steps = [
    ADD(docker / 'requirements.txt'),
    ADD(docker / 'requirements-test.txt'),
    RUN(pip('pip', 'cython', files=['requirements.txt'])),
    RUN(pip(files=['requirements-test.txt']))  # pandas requires numpy
]

for arch in ['amd64', 'arm64v8']:
    # UBUNTU
    for version in ['16.04', '18.04']:
        os = f'ubuntu-{version}'
        base = f'{arch}/ubuntu:{version}'

        cpp = DockerImage('cpp', base=base, arch=arch, os=os, steps=[
            RUN(apt(*ubuntu_pkgs))
        ])
        python = DockerImage('python', base=cpp, steps=python_steps)

        cpp_worker = DockerImage('cpp', base=cpp, tag='worker',
                                 steps=worker_steps)
        python_worker = DockerImage('python', base=python, tag='worker',
                                    steps=worker_steps)

        images.extend([cpp, python, cpp_worker, python_worker])

    # ALPINE
    for version in ['3.9']:
        os = f'alpine-{version}'
        base = f'{arch}/alpine:{version}'

        cpp = DockerImage('cpp', base=base, arch=arch, os=os, steps=[
            RUN(apk(*alpine_pkgs)),
            RUN('python -m ensurepip'),
        ])
        python = DockerImage('python', base=cpp, steps=python_steps)

        cpp_worker = DockerImage('cpp', base=cpp, tag='worker',
                                 steps=worker_steps)
        python_worker = DockerImage('python', base=python, tag='worker',
                                    steps=worker_steps)

        images.extend([cpp, python, cpp_worker, python_worker])

# CONDA
for arch in ['amd64']:
    os = 'ubuntu-18.04'
    base = f'{arch}/ubuntu:18.04'
    steps = [
        RUN(apt('wget')),
        # install miniconda
        ENV(PATH='/opt/conda/bin:$PATH'),
        ADD(docker / 'install_conda.sh'),
        RUN('/install_conda.sh', arch, '/opt/conda'),
        # install cpp dependencies
        ADD(docker / 'conda-linux.txt'),
        ADD(docker / 'conda-cpp.txt'),
        RUN(conda(files=['conda-linux.txt', 'conda-cpp.txt'])),
        # load .bashrc and run conda init
        ENTRYPOINT(['/bin/bash', '-i', '-c'])
    ]
    cpp = DockerImage('cpp', base=base, arch=arch, os=os, variant='conda',
                      steps=steps)
    cpp_worker = DockerImage('cpp', base=cpp, tag='worker',
                             steps=conda_worker_steps)
    images.extend([cpp, cpp_worker])

    for pyversion in ['2.7', '3.6', '3.7']:
        repo = f'{arch}-conda-python-{pyversion}'
        name = f'python-{pyversion}'
        python = DockerImage(name, base=cpp, steps=[
            ADD(docker / 'conda-python.txt'),
            RUN(conda(f'python={pyversion}', files=['conda-python.txt']))
        ])
        python_worker = DockerImage(name, base=python, tag='worker',
                                    steps=conda_worker_steps)
        images.extend([python, python_worker])

# TODO(kszucs): We need to bookeep a couple of flags to each image, like
#               the architecture and required nvidia-docker runtime to
#               pair with the docker daemons on the worker machines
arrow_images = images
worker_images = [i for i in images if i.tag == 'worker']
