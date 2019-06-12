[![Build Status](https://travis-ci.org/ursa-labs/ursabot.svg?branch=master)](https://travis-ci.org/ursa-labs/ursabot)

# Ursa Labs' buildbot configuration for Apache Arrow

Ursabot is a continous integration application based on the
[buildbot][buildbot-docs] framework. The primary focus of ursabot is to
execute various builds benchmark and packaging tasks for
[Apache Arrow][arrow-url].


## Arrow's build system

Arrow is used on a wide range of platforms, it has libraries in many languages,
and these all have multiple build options and compiler flags. We want to ensure
that patches don't break a build -- preferably before merging them -- and we
want to ensure that we don't regress.
While we use Travis-CI and Appveyor for some build testing, we can't test on
all platforms there, and there is some inefficiency because it is difficult to
express build stage dependencies and collect build artifacts (for example, of
the C++ library for use in Python/R/etc.).

Similarly, we want to prevent performance regressions and aim to prevent
merging patches that degrade performance, and in order to do this, we need to
run benchmarks. These benchmarks can't reliably be run on public CI
infrastructure because they need dedicated, consistent hardware in order to
return comparable results.

To ensure the quality of the software we ship, and to facilitate Arrow
developers and maintainers, we have a system of scripts and automation that
perform key functions. This document outlines the goals of our build and
automation system and describes how to work with it, as it is currently
implemented.

### Goals

- Prevent "breaking the build". For a given patch, run all tests and
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
  worthwhile.


### Out of scope

These have been discussed and would be valuable, but they are definitely
"nice to haves" and should be deferred until the primary goals are met.

- Database for storing benchmark results
- Central station for hosting the build artifacts
- Dashboard showing build health across all platforms and configurations


## Implementation

Currently We have a three-tiered system.

- Use Travis-CI and Appveyor for a set of language/build configurations that
  run on every commit and pull request on GitHub. The configuration files are
  maintained in the [arrow][arrow-repo] repository.
- [Crossbow][crossbow-readme] for binary
  packaging and nightly tests. Crossbow provides a command line interface to
  programatically trigger Travis and Appveyor builds by creating git branches
  in [ursalabs/crossbow][crossbow-repo] repository.
  It is maintained within [arrow][arrow-repo], for more see its
  [guide][crossbow-readme].
- [Ursabot][ursabot-repo] implemented on top of [buildbot][buildbot-docs] CI
  framework, hosted at [ci.ursalabs.org][ursabot-url] on Ursalabs' servers.
  It provides:

    - A set of builds testing the C++ implementation and Python bindings on
      multiple operating systems and architectures (most of these are executed
      automatically on each commit and pull request).
    - On-demand builds requested by commenting on a pull request.
    - On-demand benchmarks requested by commenting on a pull request, the
      benchmark results are reported as github comments. The recently developed
      [Archery][archery-readme] command-line tool is responsible for running
      and comparing the benchmarks.
    - Special builds for triggering other systems' builds, like
      [crossbow][crossbow-readme]'s packaging tasks by commenting on a pull
      request.

 <!-- Comprehensive, automatic nightly checks allow us to catch quickly any
regressions that our human expertise missed so that we can fix them right away.
(Call it "continual integration" rather than "continuous integration".) -->


## Driving Ursabot

Allowing PR reviewers to request additional checks on demand within the review
process makes it easier for us to apply extra scrutiny at review time while
also conserving CI bandwidth by using human expertise to know which checks are
needed.

### via Comments

Ursabot receives github events through a webhook. It listens on pull request
comments mentioning @ursabot. It follows the semantics of a command line
interface, to see the available commands add a comment on the pull request: `@ursabot --help`.

The @ursabot GitHub user will respond or [react][github-reactions] that it has
started a build for you. Unfortunately, it does not currently report back
on the build status. The reporters are already implemented. They will be
enabled once the proper github integration permissions are set for the
[apache/arrow][arrow-repo] repository. Until that you have to search around the
[buildbot UI][ursabot-url] for it. The command parser is implemented in [commands.py](commands.py).

Currently available commands:

  - `@ursabot build`: Triggers all the ursabot tests. These tests are run
    automatically, but this is a convinient way to force a re-build.
  - `@ursabot benchmark`: Triggers C++ benchmarks and sends back the results as
    a github comment and highlights the regressions.
  - `@ursabot crossbow test cpp-python`: Triggers the `cpp-python` test group
    defined in [test.yml][crossbow-tests] and responds with a URL pointing to submitted crossbow branches at the github UI showing the build statuses.
  - `@ursabot crossbow package wheel conda`: Triggers the `wheel` and `conda`
    crossbow packaging groups defined in [tasks.yml][crossbow-tasks].

Note that the commands won't trigger any builds if the commit message contains
a skip pattern, like `[skip ci]` or `[ci skip]`.

### via the Web UI

You can also initiate a build for a specific architecture/configuration in the
[buildbot UI][ursabot-url]. Navigate to [Builds > Builders][ursabot-builders],
select a builder, and click `Build apache/arrow` buttin at the top right. This triggers the force schedulers where you can specify a branch and/or commit to
build. In the future specialized builders will have different fields to provide
the neccessary information.

### via CLI

Buildbot supports submitting local patches directly to the cluster and
triggering specific builders. The `TryScheduler` is a really handy way to test
local changes without polluting the git history:

```bash
buildbot try \
  --connect=pb \
  --master=... \
  --username=... \
  --passwd=... \
  --get-builder-names
```

If someone wants to use this feature then please raise an issue, because it requires custom credentials.

## Running Ursabot

Intallation requires at least Python 3.6:

```bash
pip install -e ursabot
```

Define the configuration environment (prod|test) and start the service:

```bash
$ export USABOT_ENV=test  # this is the default
$ buildbot restart ursabot
$ tail -f ursabot/twisted.log
```


## Configuring Ursabot

The buildbot configuration is implemented in `master.cfg`, however to turn
services on and off more easily, add workers without touching any python
file, and provide credentials without committing to git there is another
static configuration layer constructed by `default.toml`, `test.toml`
and `prod.toml` files.
These files are loaded as plain dictionaries and merged upon each other
depending on the `URSABOT_ENV` variable. The merge order is:

1. [`default.toml`](default.toml)
2. `$URSABOT_ENV.toml` like [`test.toml`](test.toml) or [`prod.toml`](prod.toml)
3. `local.toml` [optional]
4. `.secrets.toml` [optional]

For the available configuration keys see [`default.toml`](default.toml).
The preferred secret handling method is to setup a secret provider like
`SecretInPass`, see the `secrets` configuration key in
[`default.toml`](default.toml).


### Adding a new build(er)s

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


## Define docker images

Arrow supports multiple platforms, has a wide variety of features thus a lot of
dependencies. Installing them in each build would be time and resource
consuming, so ursabot ships docker images for reusability.

There is a small docker utility in `ursabot.docker` module to define
hierachical images. A small example to demonstrate it:

```python
from ursabot.docker import DockerImage, ImageCollection
from ursabot.docker import RUN, ENV, CMD, ADD, apt, conda


miniconda = DockerImage(
    name='conda',
    base='continuumio/miniconda3',
    arch='amd64',
    os='debian-9'
)
pandas = DockerImage(
    name='pandas',
    base=miniconda,
    steps=[
        RUN(conda('pandas'))
    ]
)
pyarrow = DockerImage(
    name='pyarrow',
    base=miniconda,
    steps=[
        RUN(conda('pyarrow'))
    ]
)

images = ImageCollection([miniconda, pandas, pyarrow])

# create a docker image for each of the previous ones running jupyter notebook
jupyter_steps = [
    RUN(conda('jupyter')),
    CMD([
        'jupyter', 'notebook',
        '--ip', '0.0.0.0',
        '--no-browser',
        '--allow-root'
    ])
]
images.extend(
    DockerImage(
        name=image.name,
        base=image,
        tag='jupyter',
        steps=jupyter_steps
    )
    for image in images
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

Most of the dependency requirements are factored out to easily editable text
files under the [docker](docker) directory.

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

### Adding new workers to the cluster

Adding docker latent workers requires a worker entry in the configuration.
Name, architecture and a docker host (accessable by the buildmaster) are
required, see an example in [default.toml](default.toml).
Adding non-docker workers are also possible, but must register them in the
[master.cfg](master.cfg).

## Developing Ursabot

Buildbot doesn't distribute its testing suite with binary wheels, so in order
to run the unit tests buildbot must be installed from source:

```bash
pip install --no-binary buildbot -e .
pytest -v ursabot
```

### Pre-commit hooks

Install [pre-commit](https://pre-commit.com/) then to setup the git
[hooks](.pre-commit-config.yaml) run `pre-commit install`.


## Possible further improvements

- Project abstraction to reduce the complexity of [master.cfg](master.cfg)
- Multi-master setup for scaling
- Setup WAMP/Crossbar to restart the buildmaster without cancelling the running
  builds
- Windows containers and workers (docker in virtualized nodes)
- Enable CUDA docker runtime (builder is already added)
- Crossbow poller to report back crossbow task statuses


[arrow-repo]: https://github.com/apache/arrow
[arrow-url]: https://arrow.apache.org
[archery-readme]: https://github.com/apache/arrow/tree/master/dev/archery
[crossbow-readme]: https://github.com/apache/arrow/tree/master/dev/tasks
[crossbow-repo]: https://github.com/ursa-labs/crossbow
[crossbow-tests]: https://github.com/apache/arrow/blob/master/dev/tasks/tests.yml#L55
[crossbow-tasks]: https://github.com/apache/arrow/blob/master/dev/tasks/tasks.yml#L21
[ursabot-repo]: https://github.com/ursa-labs/ursabot
[ursabot-url]: https://ci.ursalabs.org
[ursabot-builders]: https://ci.ursalabs.org/#/builders
[buildbot-docs]: https://docs.buildbot.net
[github-reactions]: https://help.github.com/en/articles/about-conversations-on-github#reacting-to-ideas-in-comments
