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

Testing `Ursabot Python 3.7` builder on master:

```bash
$ ursabot project build 'Ursabot Python 3.7'
```

Testing `Ursabot Python 3.7` builder with github pull request number 140:

```bash
$ ursabot project build -pr 140 'Ursabot Python 3.7'
```

Testing `Ursabot Python 3.7` with local repository:

```bash
# upcoming feature
```

Passing multiple buildbot properties for the build:

```bash
$ ursabot project build -p prop=value -p myprop=myvalue 'Ursabot Python 3.7'
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

TODO(kszucs): more verbose readme
