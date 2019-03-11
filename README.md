[![Build Status](https://travis-ci.org/ursa-labs/ursabot.svg?branch=master)](https://travis-ci.org/ursa-labs/ursabot)


# Ursa Labs Buildmaster configuration

Doesn't contain the "actual" configuration yet, because it's filled with
sensitive data.

## Installation

```bash
pip install ursabot
```

## Docker build tool

Ursabot has a CLI interface to build the worker docker images:

```bash
ursabot docker build --help
```

To build and push `amd64` `conda` images:

```bash
ursabot docker build -a amd64 -f conda -p
```

## Development

```bash
pip install -e .
pytest -v ursabot
```

### Pre-commit hooks

Install [pre-commit](https://pre-commit.com/) than install the
[hooks](.pre-commit-config.yaml) with `pre-commit install`.
