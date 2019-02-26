from pathlib import Path
from functools import wraps
from operator import methodcaller
from textwrap import indent, dedent

from dask import delayed
# from dask.diagnostics import ProgressBar

from dockermap.api import DockerFile, DockerClientWrapper
from dockermap.shortcuts import mkdir


class DockerFile(DockerFile):

    def __str__(self):
        return self.fileobj.getvalue().decode('utf-8')


class DockerImage:

    def __init__(self, repo, base, tag='latest', steps=tuple()):
        if isinstance(base, DockerImage):
            base = base.repo
        elif not isinstance(base, str):
            raise TypeError(
                '`tag` argument must be an instance of DockerImage or str'
            )

        if not isinstance(repo, str):
            raise TypeError('`repo` argument must be an instance of str')
        if not isinstance(tag, str):
            raise TypeError('`tag` argument must be an instance of str')

        if not isinstance(steps, (tuple, list)):
            raise TypeError(
                '`steps` argument must be an instance of list or tuple'
            )
        elif not all(callable(step) for step in steps):
            raise TypeError(
                'each `step` must be a callable, use `run` function'
            )

        self.id = None
        self.tag = tag
        self.repo = repo
        self.base = base
        self.steps = steps

    def __repr__(self):
        return f'<DockerImage: {self.repo}:{self.tag} at {id(self)}>'

    @property
    def dockerfile(self):
        df = DockerFile(self.base)
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
        self.id = client.build_from_file(self.dockerfile, self.repo, **kwargs)
        return self.id

    def push(self, org, repo=None, tag=None, client=None, **kwargs):
        if client is None:
            client = DockerClientWrapper()

        # ensure it's tagged
        repo = f'{org}/{self.repo}'
        client.tag(self.id, repo, self.tag)

        return client.push(repo, tag=tag, **kwargs)


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


def CMD(command):
    return lambda df: setattr(df, 'command', command)


def WORKDIR(workdir):
    return lambda df: setattr(df, 'command_workdir', workdir)


def USER(username):
    return lambda df: setattr(df, 'command_user', username)


def SHELL(shell):
    return lambda df: setattr(df, 'shell', shell)


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


# define the docker images


images = []
envs = Path('envs')
scripts = Path('scripts')


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
    'flex'
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
worker_steps = [
    RUN(pip('buildbot-worker')),
    RUN(mkdir('/buildbot')),
    ADD('buildbot.tac', '/buildbot/buildbot.tac'),
    WORKDIR('/buildbot'),
    CMD('twistd --pidfile= -ny buildbot.tac')
]


collect = delayed(list)
DelayedDockerImage = delayed(DockerImage)


for arch in ['amd64', 'arm64v8']:
    # UBUNTU
    for version in ['16.04', '18.04', '18.10']:
        prefix = f'{arch}-ubuntu-{version}'
        base = f'{arch}/ubuntu:{version}'

        cpp = DelayedDockerImage(f'{prefix}-cpp', base=base, steps=[
            RUN(apt(*ubuntu_pkgs))
        ] + worker_steps)

        python = DelayedDockerImage(f'{prefix}-python', base=cpp, steps=[
            ADD(envs / 'requirements.txt'),
            RUN(pip(files=['requirements.txt']))
        ])

        images.extend([cpp, python])

    # ALPINE
    for version in ['3.8', '3.9']:
        prefix = f'{arch}-alpine-{version}'
        base = f'{arch}/alpine:{version}'

        cpp = DelayedDockerImage(f'{prefix}-cpp', base=base, steps=[
            RUN(apk(*alpine_pkgs)),
            RUN('python -m ensurepip'),
        ] + worker_steps)

        python = DelayedDockerImage(f'{prefix}-python', base=cpp, steps=[
            ADD(envs / 'requirements.txt'),
            RUN(pip(files=['requirements.txt']))
        ])

        images.extend([cpp, python])

# CONDA
for arch in ['amd64']:
    base = f'{arch}/ubuntu:18.04'

    cpp = DelayedDockerImage(f'{arch}-conda-cpp', base=base, steps=[
        RUN(apt('wget')),
        # install miniconda
        ENV(PATH='/opt/conda/bin:$PATH'),
        ADD(scripts / 'install_conda.sh'),
        RUN('/install_conda.sh', arch, '/opt/conda'),
        # install cpp dependencies
        ADD(envs / 'conda-linux.txt'),
        ADD(envs / 'conda-cpp.txt'),
        RUN(conda('twisted', files=['conda-linux.txt',
                                    'conda-cpp.txt']))
    ] + worker_steps)

    images.append(cpp)

    for pyversion in ['2.7', '3.6', '3.7']:
        repo = f'{arch}-conda-python-{pyversion}'
        python = DelayedDockerImage(repo, base=cpp, steps=[
            ADD(envs / 'conda-python.txt'),
            RUN(conda(f'python={pyversion}', files=['conda-python.txt']))
        ])
        images.append(python)


# TODO(kszucs): We need to bookeep a couple of flags to each image, like
#               the architecture and required nvidia-docker runtime to
#               pair with the docker daemons on the worker machines
arrow_images = images
