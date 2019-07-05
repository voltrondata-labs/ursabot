# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import json
import logging
from pathlib import Path
from functools import wraps
from operator import methodcaller
from textwrap import indent, dedent

# from dask import delayed
from toposort import toposort
from dockermap.api import DockerFile, DockerClientWrapper
from dockermap.shortcuts import mkdir
from dockermap.build.dockerfile import format_command

from .utils import Collection, read_dependency_list


logger = logging.getLogger(__name__)


class DockerFile(DockerFile):

    def __str__(self):
        return self.fileobj.getvalue().decode('utf-8')


class DockerImage:
    """Docker image abstraction for image hierarchies with strict naming

    Parameters
    ----------
    name : str
        Short name, identifier of the image. Prefer short names, because the
        generated repository name will end with the image's name.
    base : Union[str, DockerImage]
        Either a string used to defined root nodes in the image hierarchy or
        another DockerImage instance. In the former case `arch` and `os`
        arguments must be passed explicitly, whereas in the latter case these
        properties are inherited from the base (parent) image.
    title : str, default None
        A more human friendly title for the image.
    org : str, default None
        Docker organization the image should belong to.
    tag : str, default 'latest'
        Docker tag for the image.
    arch : 'amd64' or 'arm64v8', default None
        Docker architecture of the image. Currently only 'amd64' and 'arm64v8'
        values are supported.
    os : str, default None
        Operating system of the image. Examples: 'ubuntu-18.04', 'alpine-3.9'.
    runtime : str, default None
        Docker runtime the image should be run with, e.g. nvidia for the CUDA
        images. This property doesn't affect the image, only the running
        container.
    steps : List[Callable[[dockermap.api.DockerFile], None]], default []
        List of steps defined in docker-ish DSL. Use functions like ADD, RUN,
        ENV, WORKDIR, USER, CMD, ENTRYPOINT, SHELL.

    Examples
    --------
    In [1]: from ursabot.docker import DockerImage, RUN, CMD, conda

    In [2]: miniconda = DockerImage(
       ...:     'conda',
       ...:     base='continuumio/miniconda3',
       ...:     arch='amd64',
       ...:     os='debian-9'
       ...: )

    In [3]: jupyter = DockerImage(
       ...:     'jupyter',
       ...:     base=miniconda,
       ...:     steps=[
       ...:         RUN(conda('jupyter')),
       ...:         CMD(['jupyter', 'notebook',
       ...:             '--ip', '0.0.0.0',
       ...:             '--no-browser',
       ...:             '--allow-root'])
       ...:     ]
       ...: )

    In [4]: miniconda
    Out[4]: <DockerImage: amd64-debian-9-conda:latest at 4456735912>

    In [5]: jupyter
    Out[5]: <DockerImage: amd64-debian-9-jupyter:latest at 4456320976>

    In [6]: miniconda.build()
    Out[6]: <DockerImage: amd64-debian-9-conda:latest at 4456735912>

    In [7]: jupyter.build()
    Out[7]: <DockerImage: amd64-debian-9-jupyter:latest at 4456320976>
    """

    def __init__(self, name, base, title=None, org=None, tag='latest',
                 arch=None, os=None, variant=None, runtime=None,
                 steps=tuple()):
        if isinstance(base, DockerImage):
            if not title:
                title = base.title
            if not org:
                org = base.org
            if not runtime:
                runtime = base.runtime
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

        string_args = {'org': org, 'name': name, 'tag': tag, 'os': os,
                       'title': title, 'variant': variant, 'runtime': runtime}
        optional_args = {'org', 'title', 'variant', 'runtime'}
        for k, v in string_args.items():
            if v is None and k in optional_args:
                continue
            if not isinstance(v, str):
                raise TypeError(f'`{k}` argument must be an instance of str')

        if arch not in {'amd64', 'arm64v8', 'arm32v7'}:
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
        self.title = title
        self.base = base
        self.org = org
        self.tag = tag
        self.arch = arch
        self.os = os
        self.variant = variant
        self.runtime = runtime
        self.steps = tuple(steps)

    def __str__(self):
        return self.fqn

    def __repr__(self):
        return f'<DockerImage: {self.fqn} at {id(self)}>'

    def __hash__(self):
        return hash((self.name, self.tag, self.steps))

    @property
    def fqn(self):
        """Return the fully qualified name including organization and tag"""
        if self.org:
            return f'{self.org}/{self.repo}:{self.tag}'
        else:
            return f'{self.repo}:{self.tag}'

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
        """Build the docker images

        Parameters
        ----------
        client : dockermap.api.DockerClientWrapper, default None
            Docker client to build the images with. For example it can be
            used to build images on another host.
        """
        if client is None:
            client = DockerClientWrapper()

        # wrap it in a try catch and serialize the failing dockerfile
        # also consider to use add an `org` argument to directly tag the image
        # TODO(kszucs): pass platform argument
        logger.info(f'Start building {self.fqn}')
        client.build_from_file(self.dockerfile, self.fqn, **kwargs)
        logger.info(f'Image has been built successfully: {self.fqn}')

        return self

    def push(self, client=None, **kwargs):
        if client is None:
            client = DockerClientWrapper()

        client.push(self.fqn, **kwargs)
        return self


class ImageCollection(Collection):

    def build(self, *args, **kwargs):
        deps = dict()
        for image in self:
            # image.base is either a string or a DockerImage, in the former
            # case it is going to be pulled from the registry instead of
            # being built by us
            if image not in deps:
                deps[image] = set()
            if isinstance(image.base, DockerImage):
                deps[image].add(image.base)

        for image_set in toposort(deps):
            # TODO(kszucs): this can be easily parallelized with dask
            for image in image_set:
                image.build(*args, **kwargs)

    def push(self, *args, **kwargs):
        # topological sort is not required because the layers are cached
        for image in self:
            image.push(*args, **kwargs)


# functions to define dockerfiles from python


_tab = ' ' * 4


@wraps(DockerFile.add_file, ('__doc__',))
def ADD(*args, **kwargs):
    return methodcaller('add_file', *args, **kwargs)


@wraps(DockerFile.add_file, ('__doc__',))
def COPY(src, dst, from_image=None, **kwargs):
    if from_image:
        args = ['--from={}'.format(from_image), src, dst]
        return methodcaller('prefix', 'COPY', args)
    else:
        return ADD(src, dst, **kwargs)


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
    assert isinstance(shell, list)
    return _command('SHELL', shell)


# command shortcuts


def symlink(mapping):
    # mapping of target => original
    cmds = ['ln -sf {} {}'.format(v, k) for k, v in mapping.items()]
    delim = ' && \\\n{}'.format(_tab)
    return delim.join(cmds)


def apt(*packages):
    """Generates apt install command"""
    template = dedent("""
        apt-get update -y -q && \\
        apt-get install -y -q \\
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


# configure shell and entrypoint to load .bashrc
docker_assets = Path(__file__).parent.parent / 'docker'
python_symlinks = {'/usr/local/bin/python': '/usr/bin/python3',
                   '/usr/local/bin/pip': '/usr/bin/pip3'}

ubuntu_pkgs = read_dependency_list(docker_assets / 'pkgs-ubuntu.txt')
alpine_pkgs = read_dependency_list(docker_assets / 'pkgs-alpine.txt')
python_steps = [
    ADD(docker_assets / 'requirements.txt'),
    ADD(docker_assets / 'requirements-test.txt'),
    RUN(pip('cython', files=['requirements.txt'])),
    RUN(pip(files=['requirements-test.txt']))
]

# Note the python has a special treatment, because buildbot requires it.
# So all of the following images must have a python interpreter and pip
# pre-installed.
images = ImageCollection()

for arch in ['amd64', 'arm64v8', 'arm32v7']:
    # UBUNTU
    for ubuntu_version in ['16.04', '18.04']:
        basetitle = f'{arch.upper()} Ubuntu {ubuntu_version}'

        cpp = DockerImage(
            name='cpp',
            base=f'{arch}/ubuntu:{ubuntu_version}',
            arch=arch,
            os=f'ubuntu-{ubuntu_version}',
            org='ursalab',
            title=f'{basetitle} C++',
            steps=[
                RUN(apt(*ubuntu_pkgs, 'python3', 'python3-pip')),
                RUN(symlink(python_symlinks))
            ]
        )
        python = DockerImage(
            name='python-3',
            base=cpp,
            title=f'{basetitle} Python 3',
            steps=python_steps
        )
        images.extend([cpp, python])

        if ubuntu_version in {'18.04'}:
            cpp_benchmark = DockerImage(
                name='cpp-benchmark',
                base=cpp,
                title=f'{basetitle} C++ Benchmark',
                steps=[
                    RUN(apt('libbenchmark-dev')),
                    RUN(pip('click', 'pandas'))
                ]
            )
            images.append(cpp_benchmark)

    # ALPINE
    for alpine_version in ['3.9']:
        basetitle = f'{arch.upper()} Alpine {alpine_version}'

        cpp = DockerImage(
            name='cpp',
            base=f'{arch}/alpine:{alpine_version}',
            arch=arch,
            os=f'alpine-{alpine_version}',
            title=f'{basetitle} C++',
            org='ursalab',
            steps=[
                RUN(apk(*alpine_pkgs, 'python3-dev', 'py3-pip')),
                RUN(symlink(python_symlinks))
            ]
        )
        python = DockerImage(
            name='python-3',
            base=cpp,
            title=f'{basetitle} Python 3',
            steps=python_steps
        )
        images.extend([cpp, python])

# CONDA
for arch in ['amd64']:
    basetitle = f'{arch.upper()} Conda'

    base = DockerImage(
        name='base',
        base=f'{arch}/ubuntu:18.04',
        arch=arch,
        os='ubuntu-18.04',
        variant='conda',
        org='ursalab',
        title=basetitle,
        steps=[
            RUN(apt('wget')),
            # install miniconda
            ENV(PATH='/opt/conda/bin:$PATH'),
            ADD(docker_assets / 'install_conda.sh'),
            RUN('/install_conda.sh', arch, '/opt/conda'),
            # run conda activate
            SHELL(['/bin/bash', '-l', '-c']),
            ENTRYPOINT(['/bin/bash', '-l', '-c']),
        ]
    )

    crossbow = DockerImage(
        name='crossbow',
        base=base,
        title=f'{basetitle} Crossbow',
        steps=[
            # install crossbow dependencies
            ADD(docker_assets / 'conda-crossbow.txt'),
            RUN(conda('git', 'twisted', files=['conda-crossbow.txt'])),
        ]
    )
    cpp = DockerImage(
        name='cpp',
        base=base,
        title=f'{basetitle} C++',
        steps=[
            # install cpp dependencies
            ADD(docker_assets / 'conda-linux.txt'),
            ADD(docker_assets / 'conda-cpp.txt'),
            RUN(conda(files=['conda-linux.txt', 'conda-cpp.txt'])),
        ]
    )
    cpp_benchmark = DockerImage(
        name='cpp-benchmark',
        base=cpp,
        title=f'{basetitle} C++ Benchmark',
        steps=[
            RUN(conda('benchmark', 'click', 'pandas'))
        ]
    )
    images.extend([crossbow, cpp, cpp_benchmark])

    for python_version in ['2.7', '3.6', '3.7']:
        python = DockerImage(
            name=f'python-{python_version}',
            base=cpp,
            title=f'{basetitle} Python {python_version}',
            steps=[
                ADD(docker_assets / 'conda-python.txt'),
                RUN(conda(f'python={python_version}',
                          files=['conda-python.txt']))
            ]
        )
        images.append(python)

# CUDA
for arch in ['amd64']:
    for toolkit_version in ['10.0']:
        basetitle = f'{arch.upper()} Nvidia Cuda {toolkit_version}'

        cpp = DockerImage(
            name='cpp',
            base=f'nvidia/cuda:{toolkit_version}-devel-ubuntu18.04',
            arch=arch,
            os=f'ubuntu-18.04',
            org='ursalab',
            variant='cuda',
            # used to run containers with `docker run --runtime=nvidia`
            runtime='nvidia',
            title=f'{basetitle} C++',
            steps=[
                RUN(apt(*ubuntu_pkgs, 'python3', 'python3-pip')),
                RUN(symlink(python_symlinks))
            ]
        )
        python = DockerImage(
            name='python-3',
            base=cpp,
            title=f'{basetitle} Python 3',
            steps=python_steps
        )
        images.extend([cpp, python])

# JAVA
for arch in ['amd64']:
    maven_version = 3

    for java_version in ['8', '11']:
        java = DockerImage(
            name=f'java-{java_version}',
            base=f'{arch}/maven:{maven_version}-jdk-{java_version}',
            arch=arch,
            os=f'debian-9',
            org='ursalab',
            title=f'{arch.upper()} Java OpenJDK {java_version}',
            steps=[
                RUN(apt('python3', 'python3-pip')),
                RUN(symlink(python_symlinks))
            ]
        )
        images.append(java)

# GO
for arch in ['amd64']:
    for go_version in ['1.12.6', '1.11.11']:
        go = DockerImage(
            name=f'go-{go_version}',
            base=f'{arch}/golang:{go_version}-stretch',
            arch=arch,
            os=f'debian-9',
            org='ursalab',
            title=f'{arch.upper()} Debian 9 Go {go_version}',
            steps=[
                RUN(apt('python3', 'python3-pip')),
                RUN(symlink(python_symlinks))
            ]
        )
        images.append(go)

# RUST
for arch in ['amd64']:
    for rust_version in ['1.35']:
        rust = DockerImage(
            name=f'rust-{rust_version}',
            base=f'{arch}/rust:{rust_version}-stretch',
            arch=arch,
            os=f'debian-9',
            org='ursalab',
            title=f'{arch.upper()} Debian 9 Rust {rust_version}',
            steps=[
                RUN(apt('python3', 'python3-pip')),
                RUN(symlink(python_symlinks))
            ]
        )
        images.append(rust)

# URSABOT
ursabot = DockerImage(
    name='ursabot',
    base='python:3.7',
    arch='amd64',
    os='debian-9',
    org='ursalab',
    title='Ursabot Python 3.7',
    steps=[
        ADD(docker_assets / 'requirements-ursabot.txt'),
        RUN(pip(files=['requirements-ursabot.txt']))
    ]
)
images.append(ursabot)

# none of the above images are usable as buildbot workers until We install,
# configure and set it as the command of the docker image
worker_command = 'twistd --pidfile= -ny buildbot.tac'
worker_steps = [
    RUN(pip('buildbot-worker')),
    RUN(mkdir('/buildbot')),
    ADD(docker_assets / 'buildbot.tac', '/buildbot/buildbot.tac'),
    WORKDIR('/buildbot')
]

# create worker images and add them to the list of arrow images
worker_images = []
for image in images:
    # exec form is required for conda images becase of the bash entrypoint
    cmd = [worker_command] if image.variant == 'conda' else worker_command
    steps = worker_steps + [CMD(cmd)]
    worker = DockerImage(image.name, base=image, tag='worker', steps=steps)
    worker_images.append(worker)

images.extend(worker_images)
