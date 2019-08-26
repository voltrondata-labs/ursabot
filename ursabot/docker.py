# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import json
import logging
import collections
from pathlib import Path
from functools import wraps
from operator import methodcaller
from textwrap import indent, dedent
from contextlib import contextmanager

from toposort import toposort
from dockermap.api import DockerFile, DockerClientWrapper
from dockermap.shortcuts import mkdir
from dockermap.build.dockerfile import format_command

from .utils import Platform, Filter

__all__ = [
    'DockerFile',
    'DockerImage',
    'ImageCollection',
    'worker_image_for',
    'ADD',
    'COPY',
    'RUN',
    'ENV',
    'WORKDIR',
    'USER',
    'CMD',
    'ENTRYPOINT',
    'SHELL',
    'symlink',
    'apt',
    'apk',
    'pip',
    'conda'
]

logger = logging.getLogger(__name__)


class DockerClientWrapper(DockerClientWrapper):

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()


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
    platform : Platform, default None
        Metadata describing the platform of the image.
    steps : List[Callable[[dockermap.api.DockerFile], None]], default []
        List of steps defined in docker-ish DSL. Use functions like ADD, RUN,
        ENV, WORKDIR, USER, CMD, ENTRYPOINT, SHELL.

    Examples
    --------
    In [1]: from ursabot.docker import DockerImage, RUN, CMD, conda

    In [2]: miniconda = DockerImage(
       ...:     'conda',
       ...:     base='continuumio/miniconda3',
       ...:     platform=Platform(arch='amd64', distro='debian', version='9')
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

    __slots__ = ('name', 'title', 'base', 'tag', 'org', 'platform', 'variant',
                 'steps')

    def __init__(self, name, base, title=None, org=None, tag='latest',
                 platform=None, variant=None, steps=tuple()):
        if isinstance(base, DockerImage):
            if not title:
                title = base.title
            if not org:
                org = base.org
            if platform is not None and platform != base.platform:
                raise ValueError(
                    f'Given platform `{platform}` is not equal with the base '
                    f'platform of the image: `{base.platform}`'
                )
            platform = base.platform
            variant = variant or base.variant
        elif not isinstance(base, str):
            raise TypeError(
                '`tag` argument must be an instance of DockerImage or str'
            )

        string_args = {'org': org, 'name': name, 'tag': tag, 'title': title,
                       'variant': variant}
        optional_args = {'org', 'title', 'variant'}
        for k, v in string_args.items():
            if v is None and k in optional_args:
                continue
            if not isinstance(v, str):
                raise TypeError(f'`{k}` argument must be an instance of str')

        if not isinstance(steps, (tuple, list)):
            raise TypeError(
                '`steps` argument must be an instance of list or tuple'
            )
        elif not all(callable(step) for step in steps):
            raise TypeError(
                'each `step` must be a callable, use `run` function'
            )

        if not isinstance(platform, Platform):
            raise TypeError(
                f'`platform` argument must be an instance of Platform'
            )

        self.name = name
        self.title = title
        self.base = base
        self.tag = tag
        self.org = org
        self.platform = platform
        self.variant = variant
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
        if self.variant is None:
            return f'{self.platform}-{self.name}'
        else:
            return f'{self.platform}-{self.variant}-{self.name}'

    @property
    def dockerfile(self):
        # self.base is either a string or a DockerImage instance
        df = DockerFile(str(self.base))
        for callback in self.steps:
            callback(df)
        df.finalize()
        return df

    @property
    def workdir(self):
        return self.dockerfile.command_workdir

    def save_dockerfile(self, directory):
        path = Path(directory) / f'{self.repo}.{self.tag}.dockerfile'
        self.dockerfile.save(path)

    @contextmanager
    def _client(self, client=None):
        if client is None:
            with DockerClientWrapper() as client:
                yield client
        else:
            yield client

    def build(self, client=None, **kwargs):
        """Build the docker images

        Parameters
        ----------
        client : dockermap.api.DockerClientWrapper, default None
            Docker client to build the images with. For example it can be
            used to build images on another host.
        """
        logger.info(f'Start building {self.fqn}')
        with self._client(client) as client:
            client.build_from_file(self.dockerfile, self.fqn, **kwargs)
        logger.info(f'Image has been built successfully: {self.fqn}')

        return self

    def push(self, client=None, **kwargs):
        with self._client(client) as client:
            client.push(self.fqn, **kwargs)
        return self


class ImageCollection(list):

    def _image_dependents(self):
        """Returns an mapping of image => {parents}

        Including parent images not originally part of the collection.
        """
        deps = collections.defaultdict(set)
        stack = collections.deque(self)
        while stack:
            # image.base is either a string or a DockerImage, in the former
            # case it is going to be pulled from the registry instead of
            # being built by us, in the latter case we need to traverse
            # the parents
            image = stack.pop()
            parents = deps[image]
            if isinstance(image.base, DockerImage):
                parents.add(image.base)
                if image.base not in deps:
                    stack.append(image.base)
        return deps

    def build(self, *args, **kwargs):
        deps = self._image_dependents()
        for image_set in toposort(deps):
            # TODO(kszucs): this can be easily parallelized with dask
            for image in image_set:
                image.build(*args, **kwargs)

    def push(self, *args, **kwargs):
        # topological sort is not required because the layers are cached
        for image in self:
            image.push(*args, **kwargs)

    def filter(self, **kwargs):
        criteria = Filter(**kwargs)
        filtered = filter(criteria, self)
        return self.__class__(filtered)


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
    args = tuple(map('='.join, kwargs.items()))
    args = indent(' \\\n'.join(args), _tab).lstrip()
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
        export DEBIAN_FRONTEND=noninteractive && \\
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


# none of the above images are usable as buildbot workers until We install,
# configure and set it as the command of the docker image
_pkg_root = Path(__file__).parent.parent
_worker_command = 'twistd --pidfile= -ny buildbot.tac'
_worker_steps = [
    RUN(pip('buildbot-worker')),
    RUN(mkdir('/buildbot')),
    ADD(_pkg_root / 'worker.tac', '/buildbot/buildbot.tac'),
    WORKDIR('/buildbot')
]


def worker_image_for(image):
    # treat conda images specially because of environment activation
    cmd = [_worker_command] if image.variant == 'conda' else _worker_command
    steps = _worker_steps + [CMD(cmd)]
    return DockerImage(image.name, base=image, tag='worker', steps=steps)
