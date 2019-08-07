# Ursabot project configuration for Arrow

This directory contains all the relevant code required to reproduce the
ursabot CI setup hosted at https://ci.ursalabs.org.

# How to validate the configurations

```bash
$ ursabot checkconfig
```

`ursabot` command loads `master.cfg` from the current directory by default, but
`--config` argument can be passed to explicitly define a configuration file.

```bash
$ ursabot -c arrow/master.cfg checkconfig
```

# How to run it locally

Firt master's database must be initialized:

```bash
$ ursabot -v upgrade-master
```

Start/stop/restart the master:

```bash
$ ursabot -v start|stop|restart
```

# Commands

Describe the loaded master configuration:

```bash
$ ursabot desc
```

Describe the loaded project configuration:

```bash
$ ursabot project desc  # for master configs with a single project
$ ursabot project -p arrow desc  # for master configs with multiple projects
```

## Commands for local reproducibility

Testing `AMD64 Conda C++` builder on master:

```bash
$ ursabot project build 'AMD64 Conda C++'
```

Testing `AMD64 Conda C++` builder with github pull request number 140:

```bash
$ ursabot project build -pr 140 'AMD64 Conda C++'
```

Testing `AMD64 Conda C++` with local repository:

```bash
$ ursabot project build -s ~/Workspace/arrow:. 'AMD64 Conda C++'
```

Where `~/Workspace/arrow` is the path of the local Arrow repository and `.`
is the destination directory under the worker's build directory (in this case:
`/buildbot/AMD64_Conda_C__/.`)

Passing multiple buildbot properties for the build:

```bash
$ ursabot project build -p prop=value -p myprop=myvalue 'AMD64 Conda C++'
```

### Attach on failure

Ursabot supports debugging failed builds with attach attaching ordinary shells
to the still running workers - where the build has previously failed.

Use the `--attach-on-failure` or `-a` flags.

```bash
$ ursabot project build --attach-on-failure `AMD64 Conda C++`
```

## Commands operating on docker images

Listing images:

```bash
$ ursabot docker list
```

Filtering images:

```bash
$ ursabot docker --arch amd64 list
$ ursabot docker --arch amd64 --variant conda list
$ ursabot docker --arch amd64 --variant conda --name cpp list
$ ursabot docker --arch amd64 --variant conda --name cpp --tag worker list
$ ursabot docker --arch amd64 --variant conda --name cpp --os debian-9 list
```

Building the images:

```bash
$ ursabot docker --arch amd64 --variant conda build
```

Pushing the images:

```bash
$ ursabot docker --arch amd64 --variant conda build --push
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
