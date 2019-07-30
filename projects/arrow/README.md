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

# Commands operating on docker images

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
