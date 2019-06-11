[![Build Status](https://travis-ci.org/ursa-labs/ursabot.svg?branch=master)](https://travis-ci.org/ursa-labs/ursabot)

# Ursa Labs' buildbot configuration for Apache Arrow


## Installation

```bash
pip install -e ursabot
```

Ursabot is a continous integration application based on the
[buildbot](http://buildbot.net/) framework. The primary focus of ursabot is to
execute various builds benchmark and packaging tasks for
[Apache Arrow](https://arrow.apache.org/).


## Configuration

The buildbot configuration is implemented in `master.cfg`, however to turn
services on and off more easily, add workers without touching any python
files, and provide credentials without committing to git there is another
static configuration layer constructed by `default.toml`, `test.toml`
and `prod.toml` files.
These files are loaded as plain dictionaries and merged upon each other
depending on the `URSABOT_ENV` variable. The merge order is:

> default.toml <- $URSABOT_ENV.toml <- .secrets.toml [optional]

For the available configuration keys see `default.toml`.


## Running a local instance of ursabot

```bash
$ export USABOT_ENV=test  # this is the default
$ buildbot restart ursabot
$ tail -f ursabot/twisted.log
```


## Adding a new build

The closest abstraction to the traditional yaml based CI configs in ursabot are
the Builders. In the simplest case a builder is defined by a sequence of steps
which are executed as shell commands on the worker.
The following example builder presumes, that `apt-get` and `git` is available
on the worker.

```python
from buildbot.plugins import util, worker
from ursabot.steps import ShellCommand
from ursabot.builders import Builder
from ursabot.schedulers import AnyBranchScheduler


class TestBuilder(Builder):
    tags = ['example-build', 'arbitrary-tag']
    steps = [
        GitHub(
            name='Clone the test repository',
            repourl='https://github.com/example/repo'
            mode='full'
        ),
        ShellCommand(
            name='Install dependencies',
            command=['apt-get', 'install', '-y'],
            args=['my', 'packages']
        ),
        ShellCommand(
            name='Execute tests',
            command=['my-custom-test-runner', util.Property('test-selector')]
        )
    ]


# in the master.cfg
local_worker = worker.LocalWorker('my-local-worker')
simple_builder = TestBuilder(
    workers=[local_worker],
    properties={
        'test-selector': 'all'
    }
)
scheduler = AnyBranchScheduler(
    name='my-scheduler-name',
    builders=[simple_builder]
)

BuildmasterConfig = {
    # ...
    'workers': [local_worker],
    'schedulers': [scheduler]
    # ...
}
```

The `DockerBuilder` provides more flexibility, faster builds and better worker
isolation, Ursabot uses `DockerBuilders` extensively.

```python
from ursabot.docker import DockerImage
from ursabot.builders import DockerBuilder
from ursabot.workers import DockerLatentWorker


miniconda = DockerImage(
    'conda',
    base='continuumio/miniconda3',
    arch='amd64',
    os='debian-9'
)


class TestDockerBuilder(Builder):
    tags = ['build-within-docker-container']
    steps = [
        # checkout the source code
        GitHub(args0),
        # execute arbitrary commands
        ShellCommand(args1),
        ShellCommand(args2),
        # ...
    ]
    images = [miniconda]


docker_worker = DockerLatentWorker(
    name='my-docker-worker'
    arch='amd64'
    password=None,
    max_builds=2,
    docker_host='unix://var/run/docker.sock',
    # `docker_image` property is set by the DockerBuilder, but image can be
    # passed explicitly and used in conjunction with a simple builder like the
    #  TestBuilder from the previous example
    image=util.Property('docker_image')
)

# instantiates builders based on the available workers, the Builder's
# images and the workers are matched based on their architecture
docker_builders = TestDockerBuilder.builders_for(
    workers=[docker_worker]
)

scheduler = AnyBranchScheduler(
    name='my-scheduler-name',
    builders=docker_builders
)

BuildmasterConfig = {
    # ...
    'workers': [docker_worker],
    'schedulers': [scheduler]
    # ...
}
```


## Docker build tool

Arrow supports multiple platforms, has a wide variety of features thus a lot of
dependencies. Installing them in each build would be time and resource
consuming, so ursabot ships docker images for reusability.

There is a small docker utility in `ursabot.docker` module to define
hierachical images. A small example to demonstrate it:

```python
from ursabot.docker import DockerImage, ImageCollection
from ursabot.docker import RUN, ENV, CMD, ADD, apt, conda


images = ImageCollection()

miniconda = DockerImage('conda', base='continuumio/miniconda3',
                        arch='amd64', os='debian-9')
pandas = DockerImage('pandas', base=miniconda, steps=[
    RUN(conda('pandas'))
])
pyarrow = DockerImage('pyarrow', base=miniconda, steps=[
    RUN(conda('pyarrow'))
])
images.extend([miniconda, pandas, pyarrow])

# create a docker image for each of the previous ones running jupyter notebook
jupyter_steps = [
    RUN(conda('jupyter')),
    CMD(['jupyter', 'notebook', '--ip', '0.0.0.0', '--no-browser',
         '--allow-root'])
]
images.extend([
    DockerImage(name=img.name, base=img, tag='jupyter', steps=jupyter_steps)
    for img in images
])

# build all of the images in topological order
images.build()

# filter the images
print(images.filter(name='pyarrow', tag='jupyter'))
```

Try running jupyter with pyarrow pre-installed:

```bash
docker run -p 8888:8888 amd64-debian-9-pyarrow:jupyter
```

Ursabot has a CLI interface to build the docker images:

```bash
ursabot docker build --help
```

To build and push Arrow C++ `amd64` `conda` images:

```bash
ursabot --verbose docker --arch amd64 --variant conda --name cpp build --push
```

To build and push all `arm64v8` `alpine` images:

```bash
ursabot --verbose \
  docker --docker-host tcp://arm-machine:2375 --arch arm64v8 --os alpine-3.9 \
  build --push
```


### Adding a new dependency to the docker images

For plain (non-conda) docker images append the appropiate package to
[pkgs-alpine.txt](docker/pkgs-alpine.txt) and
[pkgs-ubuntu.txt](docker/pkgs-ubuntu.txt).

For conda images add the newly introduced dependency either to
[conda-linux.txt](docker/conda-linux.txt),
[conda-cpp.txt](docker/conda-cpp.txt),
[conda-python.txt](docker/conda-cpp.txt) or
[conda-sphinx.txt](docker/conda-sphinx.txt)
depending on which images should contain the new dependency.

In order to add a new pip dependency to the python images edit
[requirements.txt](docker/requirements.txt) or
[requirements-test.txt](docker/requirements-test.txt).

Then build and push the new images:

```bash
$ ursabot -v docker -dh tcp://amd64-host:2375 -a amd64 build -p
$ ursabot -v docker -dh tcp://arm64-host:2375 -a arm64v8 build -p
```


## Development

Buildbot doesn't distribute its testing suite with binary wheels, so it must
be installed from source.

```bash
pip install --no-binary buildbot -e .
pytest -v ursabot
```

### Pre-commit hooks

Install [pre-commit](https://pre-commit.com/) then to setup the git
[hooks](.pre-commit-config.yaml) run `pre-commit install`.
