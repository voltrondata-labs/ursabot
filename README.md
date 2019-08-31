<!---
Copyright 2019 RStudio, Inc.
All rights reserved.

Use of this source code is governed by a BSD 2-Clause
license that can be found in the LICENSE_BSD file.
-->

[![Build Status](https://travis-ci.org/ursa-labs/ursabot.svg?branch=master)](https://travis-ci.org/ursa-labs/ursabot)

# Ursa Labs' buildbot configuration for Apache Arrow

Ursabot is a continous integration framework based on the
[buildbot][buildbot-docs] framework. The primary focus of ursabot is to
execute various builds benchmark and packaging tasks for
[Apache Arrow][arrow-url] however `ursabot` can be used for arbitrary projects.

## Notable features

- a standalone project abstraction to make the project configurations module
  and reusable, and a less verbose master configuration supporting multiple
  projects
- locally reproducible builds via command line interface
- attachable interactive shells to the docker workers in case of build failures
- local source mounting for docker workers
- declerative builder configuration and a docker builder which makes it easier
  to work with docker latent workers
- extended github hook to drive buildbot via github comments
- click based comment parser
- improved change filter to filter changes based on build properties
- reimplemented github reporters: status-, comment- and review reporters
- easily extensible formatter classes to use with the reimplemented reporters
- steps implemented based on new-style ShellCommand step
- a token rotator to use multiple github tokens with github services
- a docker image tool to maintain and build hierachical docker images
- command line interface and additional utilities

## Driving Ursabot

Allowing PR reviewers to request additional checks on demand within the review
process makes it easier for us to apply extra scrutiny at review time while
also conserving CI bandwidth by using human expertise to know which checks are
needed.

### via Comments

Ursabot receives github events through a webhook. It listens on pull request
comments mentioning @ursabot. It follows the semantics of a command line
interface, to see the available commands add a comment on the pull request:
`@ursabot --help`.

The @ursabot GitHub user will respond or [react][github-reactions] that it has
started a build for you. The command parser is implemented in
[commands.py](commands.py).

Currently available commands:

  - `@ursabot build`: Triggers all the ursabot tests. These tests are run
    automatically, but this is a convinient way to force a re-build.
  - `@ursabot benchmark`: Triggers C++ benchmarks and sends back the results as
    a github comment and highlights the regressions.
  - `@ursabot crossbow test cpp-python`: Triggers the `cpp-python` test group
    defined in [test.yml][crossbow-tests] and responds with a URL pointing to
    submitted crossbow branches at the github UI showing the build statuses.
  - `@ursabot crossbow package -g wheel -g conda`: Triggers the `wheel` and
    `conda` crossbow packaging groups defined in [tasks.yml][crossbow-tasks].
  - `@ursabot crossbow package wheel-win-cp35m wheel-win-cp36m`: Triggers only
    two tasks passed explicitly.

Note that the commands won't trigger any builds if the commit message contains
a skip pattern, like `[skip ci]` or `[ci skip]`. In order to drive ursabot
the user must have either 'OWNER', 'MEMBER' or 'CONTRIBUTOR
[roles][github-author-association].

### via the Web UI

You can also initiate a build for a specific architecture/configuration in the
[buildbot UI][ursabot-url]. Navigate to [Builds > Builders][ursabot-builders],
select a builder, and click `Build apache/arrow` buttin at the top right. This
triggers the force schedulers where you can specify a branch and/or commit to
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

If someone wants to use this feature then please raise an issue, because it
requires custom credentials.

## Install ursabot and the CLI

Running it locally helps with the development and testing new feature and/or
debugging issues without touching the production instance.

Installation requires at least Python 3.6:

```bash
cd /path/to/ursabot
pip install -e .
```

Now the `ursabot` command is available which looks for a `master.cfg` file in
the current directory. `master.cfg` can be passed explicitly via the `--config`
option:

```bash
ursabot -c path/to/master.cfg
```

Describe the loaded master configuration:

```bash
ursabot desc
```

Describe the loaded project configuration:

```bash
ursabot project desc  # for master configs with a single project
ursabot project -p arrow desc  # for master configs with multiple projects
```

## How to validate the configurations

The `checkconfig` command runs sanity checks and various validations on the
master configuration. Most of the time is `checkconfig` passes then the master
can be run successfully (unless there are some variables only available at
runtime).

```bash
ursabot checkconfig
```

`ursabot` command loads `master.cfg` from the current directory by default, but
`--config` argument can be passed to explicitly define a configuration file.

```bash
ursabot -c arrow/master.cfg checkconfig
```

The top-level `master.cfg` contains the production configuration for 
ci.ursalabs.org so it requires additional dependencies like `pass`. 
To install `pass`:

```bash
which apt && sudo -H apt install -V -y pass
which brew && brew install pass
```

## Run a local instance of Ursabot

After installation master's database must be initialized:

```bash
ursabot -v upgrade-master
```

Start/stop/restart the master:

```bash
ursabot -v start|stop|restart
```

Define the configuration environment (prod|test) and start the service:

```bash
export URSABOT_ENV=test  # this is the default
buildbot restart ursabot
tail -f ursabot/twisted.log
```

Then open `http://localhost:8100` in the browser.

## Commands for local reproducibility

Builders can be run locally without the web interface using the
`ursabot project build` command.

Testing `AMD64 Conda C++` builder on master:

```bash
ursabot project build 'AMD64 Conda C++'
```

Testing `AMD64 Conda C++` builder with github pull request number 140:

```bash
ursabot project build -pr 140 'AMD64 Conda C++'
```

Testing `AMD64 Conda C++` with local repository:

```bash
ursabot project build -s ~/Workspace/arrow:. 'AMD64 Conda C++'
```

Where `~/Workspace/arrow` is the path of the local Arrow repository and `.`
is the destination directory under the worker's build directory (in this case:
`/buildbot/AMD64_Conda_C__/.`)

Passing multiple buildbot properties for the build:

```bash
ursabot project build -p prop=value -p myprop=myvalue 'AMD64 Conda C++'
```

### Attach on failure

Ursabot supports debugging failed builds with attaching ordinary shells
to the still running workers - where the build has previously failed.

Use the `--attach-on-failure` or `-a` flags.

```bash
ursabot project build --attach-on-failure `AMD64 Conda C++`
```

## Configuring Ursabot

The buildmaster configuration happens in the `master.cfg` files. Originally
buildbot loads the dictionary called `BuildmasterConfig`, but to make it more
flexible and moduler ursabot introduces the `ProjectConfig` and `MasterConfig`
abstractions.
`ProjectConfig` contains all the relevant information for testing a project
like Apache Arrow or Ursabot itself. `ProjectConfig` can be run alone, it must
be passed to a `MasterConfig` object which provides a thin abstraction over
the original buildbot `BuildmasterConfig`. One `MasterConfig` can
[contain multiple][multiple-configs] `ProjectConfig` objects.
[Including other project configurations][Including-configs] makes it possible
to maintain the project relevant settings within the projects' repositories
instead of a decoupled one dedicated for the buildmaster.


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


repo = 'https://github.com/example/repo'


class TestBuilder(Builder):
    tags = ['example-build', 'arbitrary-tag']
    steps = [
        GitHub(
            name='Clone the test repository',
            repourl=repo,
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

project = ProjectConfig([
    name='example/repo',
    repo='https://github.com/example/repo'
    workers=[local_worker],
    builders=[simple_builder],
    schedulers=[scheduler]
])

master = MasterConfig(
    title='TestConfig',
    projects=[project]
)
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


class TestDockerBuilder(DockerBuilder):
    tags = ['build-within-docker-container']
    steps = [
        # checkout the source code
        GitHub(args0),
        # execute arbitrary commands
        ShellCommand(args1),
        ShellCommand(args2),
        # ...
    ]


docker_worker = DockerLatentWorker(
    name='my-docker-worker'
    arch='amd64'
    password=None,
    max_builds=2
)

# instantiates builders based on the available workers, the Builder's
# images and the workers are matched based on their architecture
docker_builders = TestDockerBuilder.combine_with(
    workers=[docker_worker],
    images=[miniconda]
)

scheduler = AnyBranchScheduler(
    name='my-scheduler-name',
    builders=docker_builders
)

project = ProjectConfig([
    name='example/repo',
    repo='https://github.com/example/repo'
    images=[miniconda],
    workers=[docker_worker],
    builders=docker_builders,
    schedulers=[scheduler]
])

master = MasterConfig(
    title='TestConfig',
    projects=[project]
)
```

## Define docker images

Arrow supports multiple platforms, has a wide variety of features thus a lot of
dependencies. Installing them in each build would be time and resource
consuming, so ursabot ships docker images for reusability.

There is a small docker utility in `ursabot.docker` module to define
hierachical images. It uses a DSL implemented in python instead of plain
Dockerfiles. A small example to demonstrate it:

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

To list Arrow C++ `amd64` `conda` `cpp` images:

```bash
ursabot --verbose docker --arch amd64 --variant conda --name cpp list
```

Additional filtering:

```bash
ursabot docker --arch amd64 list
ursabot docker --arch amd64 --variant conda list
ursabot docker --arch amd64 --variant conda --name cpp list
ursabot docker --arch amd64 --variant conda --name cpp --tag worker list
ursabot docker --arch amd64 --variant conda --name cpp --os debian-9 list
```

To build and push Arrow C++ `amd64` `conda` `cpp` images:

```bash
ursabot --verbose docker --arch amd64 --variant conda --name cpp build --push
```

To build and push all `arm64v8` `alpine` images:

```bash
ursabot --verbose \
  docker --docker-host tcp://arm-machine:2375 --arch arm64v8 --os alpine-3.9 \
  build --push
```

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


### Adding new workers to ci.ursalabs.org

Adding docker latent workers requires a worker entry in the `workers.yaml` configuration.
Name, architecture and a docker host (accessable by the buildmaster) are
required, see an example in [workers.yaml](workers.yaml).
Adding non-docker workers are also possible, but must register them in the
[master.cfg](master.cfg).


## Possible further improvements


These have been discussed and would be valuable, but they are definitely
"nice to haves" and should be deferred until the primary goals are met.

- Database for storing benchmark results
- Central station for hosting the build artifacts
- Dashboard showing build health across all platforms and configurations

More closely Ursabot related:

- Multi-master setup for scaling
- Setup WAMP/Crossbar to restart the buildmaster without cancelling the running
  builds
- Windows containers and workers (docker in virtualized nodes)


[arrow-repo]: https://github.com/apache/arrow
[arrow-url]: https://arrow.apache.org
[archery-readme]: https://github.com/apache/arrow/tree/master/dev/archery
[crossbow-readme]: https://github.com/apache/arrow/tree/master/dev/tasks
[crossbow-repo]: https://github.com/ursa-labs/crossbow
[crossbow-tests]: https://github.com/apache/arrow/blob/master/dev/tasks/tests.yml#L18
[crossbow-tasks]: https://github.com/apache/arrow/blob/master/dev/tasks/tasks.yml#L18
[ursabot-repo]: https://github.com/ursa-labs/ursabot
[ursabot-url]: https://ci.ursalabs.org
[ursabot-builders]: https://ci.ursalabs.org/#/builders
[buildbot-docs]: https://docs.buildbot.net
[github-reactions]: https://help.github.com/en/articles/about-conversations-on-github#reacting-to-ideas-in-comments
[github-author-association]: https://developer.github.com/v4/enum/commentauthorassociation/
[multiple-configs]: master.cfg#L137
[including-configs]: master.cfg#L36
