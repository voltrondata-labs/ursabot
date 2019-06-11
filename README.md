[![Build Status](https://travis-ci.org/ursa-labs/ursabot.svg?branch=master)](https://travis-ci.org/ursa-labs/ursabot)

# Ursa Labs' buildbot configuration for Apache Arrow

Ursabot is a continous integration application based on the
[buildbot](http://buildbot.net/) framework. The primary focus of ursabot is to
execute various builds benchmark and packaging tasks for
[Apache Arrow](https://arrow.apache.org/).

Arrow is used on a wide range of platforms, it has libraries in many languages,
and these all have multiple build options and compiler flags. We want to ensure
that patches don’t break a build--preferably before merging them--and we want
to ensure that we don’t regress. While we use Travis-CI and Appveyor for some
build testing, we can’t test on all platforms there, and there is some
inefficiency because it is difficult to express build stage dependencies and
collect build artifacts (for example, of the C++ library for use in
Python/R/etc.).

Similarly, we want to prevent performance regressions and aim to prevent
merging patches that degrade performance, and in order to do this, we need to
run benchmarks. These benchmarks can’t reliably be run on public CI
infrastructure because they need dedicated, consistent hardware in order to
return comparable results.

To ensure the quality of the software we ship, and to facilitate Arrow
developers and maintainers, we have a system of scripts and automation that
perform key functions. This document outlines the goals of our build and
automation system and describes how to work with it, as it is currently
implemented.

### Goals

- Prevent “breaking the build”. For a given patch, run all tests and
  integrations, with all relevant build configurations and on all necessary
  platforms, that might be affected by the patch.
- Prevent performance regressions
- Ensure that the release process, including building binaries, also does not
  break
- For the strongest prevention, and to reduce human cognitive burden, these
  checks should be as automated as possible.
- For faster iteration while developing and debugging, it should also be
  possible to run these checks locally

### Constraints

- CI time: running every build configuration on every commit would increase
  delays in the patch review process.
- CI compute resources: our Travis-CI bandwidth is limited, as would be any
  bespoke build cluster we maintain. Some of this can be relaxed by throwing
  money at it, but there are diminishing returns (and budget constraints).
- Dev time: whatever we invest of ourselves in building this system takes away
  from time we’d spend adding value to the Arrow project itself. To the extent
  that investing in this system saves developer time elsewhere, it is
  worthwhile, but again, there are diminishing returns.


### Implementation

We have a three-tiered system:

- Use Travis-CI and Appveyor for a minimal set of language/build configurations
  that run on every commit and pull request on GitHub.
- Use a custom CI server, ci.ursalabs.org, for additional builds on demand.

    - A GitHub integration allows them to be triggered by commenting on a pull
      request.
    - The same GitHub integration can be used for triggering benchmark runs on
      demand.

- Other build checks, particularly those that produce built artifacts
  (binaries), are run nightly.

Some, though not all, of these can be run locally.

Allowing PR reviewers to request additional checks on demand within the review
process makes it easier for us to apply extra scrutiny at review time while
also conserving CI bandwidth by using human expertise to know which checks are
needed. Comprehensive, automatic nightly checks allow us to catch quickly any
regressions that our human expertise missed so that we can fix them right away.
(Call it “continual integration” rather than “continuous integration”.)

Key components of this system:

- ci.ursalabs.org, a server in Wes’s house where we run many of these builds.
- ursabot, a customized instance of the Buildbot CI system, running on
  ci.ursalabs.org. Access its UI at https://ci.ursalabs.org/.
  Ursabot currently only has Python and C++ builds specified.
- archery, a command-line tool for running and comparing benchmarks.
- crossbow, [PLEASE FILL IN; see also https://issues.apache.org/jira/browse/ARROW-3571]


## How-to guide

### How to request ursabot builds on a PR

Add a comment on the pull request: @ursabot build. The ursabot GitHub user will
respond that it has started a build for you. Unfortunately, it does not
currently report back on the build status, or even the id of the build, so
you’ll have to search around the buildbot UI for it.

You can also initiate a build for a specific architecture/configuration in the
buildbot UI. Navigate to Builds > Builders, select a builder, and click
"Build apache/arrow" at the top right. There, you can specify a branch and/or
commit to build.

### How to add a new build job to ursabot

Define a Builder in buildbot as a subclass of DockerBuilder here. A builder has
two components: steps, a sequence of shell commands; and images, docker images
with the dependencies pre-installed to execute the steps.

The first thing to do is determine whether there already is a docker image
available to use, or whether you need to create one.

### How to add a docker image?

TBD

### How to define steps?

TBD

### How to run and test an ursabot build locally

TBD

### How to request benchmarking on a PR

Add a comment on the pull request: @ursabot benchmark. The ursabot GitHub user
will respond that it has started a build for you. (Does this one report back
the benchmark results on the PR?)

### How to run benchmarks locally

TBD write clear how-to guide; for now, read the docstrings in
https://github.com/apache/arrow/blob/master/dev/archery/archery/cli.py

### How to add another build to crossbow

TBD

### How to use crossbow build artifacts

TBD

## FAQ

- How is ursabot deployed? What happens if Wes’s server melts down and we have
  to stand it up somewhere else?
- Does ursabot run builds automatically on every commit?
  From a previous discussion, buildbot has a GitHubPullrequestPoller, and
  "The current poller is configured for a poll every 2 minutes. It polls the
  master branch and every pull requests"

    - If so, how is build status reported back to GitHub?

- How is crossbow configured? Where does it run from? On what schedule?

## Out of scope

These have been discussed and would be valuable, but they are definitely
"nice to haves" and should be deferred until the primary goals are met.

- Database for storing benchmark results
- Dashboard showing build health across all platforms and configurations
- Hosted build artifacts


## Installation

```bash
pip install -e ursabot
```

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
