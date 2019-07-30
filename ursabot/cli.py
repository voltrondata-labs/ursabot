# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import io
import sys
import logging
import toolz
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import click
from dockermap.api import DockerClientWrapper
from buildbot.config import ConfigErrors

from .configs import Config, ProjectConfig, MasterConfig
from .utils import ensure_deferred


logging.basicConfig()
logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose/--quiet', '-v', default=False, is_flag=True)
@click.option('--config-path', '-c', default='master.cfg',
              help='Configuration file path')
@click.option('--config-variable', '-cv', default='master',
              help='Variable name in the configuration which is either an '
                   ' instance of ProjectConfig or MasterConfig')
@click.pass_context
def ursabot(ctx, verbose, config_path, config_variable):
    if verbose:
        logging.getLogger('ursabot').setLevel(logging.INFO)

    stderr, stdout = io.StringIO(), io.StringIO()
    with redirect_stderr(stderr), redirect_stdout(stdout):
        config = Config.load_from(config_path, variable=config_variable)
    stderr, stdout = stderr.getvalue(), stdout.getvalue()

    if verbose:
        if stderr:
            click.echo(click.style(stderr, fg='red'), err=True)
        if stdout:
            click.echo(stdout)

    if not isinstance(config, (ProjectConfig, MasterConfig)):
        raise click.UsageError(
            f'The loaded variable `{config_variable}` from `{config_path}` '
            f'has type `{type(config)}` whereis it needs to be an instance of '
            f'either ProjectConfig or MasterConfig'
        )

    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['config'] = config
    ctx.obj['config_path'] = Path(config_path)


@ursabot.command()
@click.pass_obj
def checkconfig(obj):
    config = obj['config']
    config_path = obj['config_path']

    try:
        config.as_buildbot(filename=config_path.name)
    except ConfigErrors as e:
        click.echo(click.style('Configuration Errors:', err=True, fg='red'))
        for e in e.errors:
            click.echo(click.style(f' {e}', err=True, fg='red'))
        sys.exit(1)

    click.echo(click.style('Config file is good!', fg='green'))


@ursabot.command()
@click.pass_obj
def upgrade_master(obj):
    from buildbot.util import in_reactor
    from buildbot.scripts.upgrade_master import upgradeDatabase

    @in_reactor
    @ensure_deferred
    async def run(command_cfg, master_cfg):
        try:
            await upgradeDatabase(command_cfg, master_cfg)
        except Exception as e:
            click.error(e)

    verbose = obj['verbose']
    config = obj['config']
    config_path = obj['config_path']
    basedir = config_path.parent.absolute()

    command_cfg = {'basedir': basedir, 'quiet': not verbose}
    master_cfg = config.as_buildbot(filename=config_path.name)

    run(command_cfg, master_cfg)
    click.echo(click.style('Upgrade complete!', fg='green'))


@ursabot.command()
@click.option('--no-daemon', '-nd', is_flag=True, default=False,
              help="Don't daemonize (stay in foreground)")
@click.option('--start-timeout', is_flag=True, default=None,
              help='The amount of time the script waits for the master to '
                   'start until it declares the operation as failure')
@click.pass_obj
def start(obj, no_daemon, start_timeout):
    from buildbot.scripts.start import start

    command_cfg = {
        'basedir': obj['config_path'].parent.absolute(),
        'quiet': False,
        'nodaemon': no_daemon,
        'start_timeout': start_timeout
    }
    start(command_cfg)  # loads the config through the buildbot.tac


@ursabot.command()
@click.option('--clean', '-c', is_flag=True, default=True,
              help='Clean shutdown master')
@click.option('--no-wait', is_flag=True, default=False,
              help="Don't wait for complete master shutdown")
@click.pass_obj
def stop(obj, clean, no_wait):
    from buildbot.scripts.stop import stop
    command_cfg = {
        'basedir': obj['config_path'].parent.absolute(),
        'quiet': False,
        'clean': clean,
        'no-wait': no_wait
    }
    stop(command_cfg)


@ursabot.command()
@click.option('--no-daemon', '-nd', is_flag=True, default=False,
              help="Don't daemonize (stay in foreground)")
@click.option('--start-timeout', is_flag=True, default=None,
              help='The amount of time the script waits for the master to '
                   'start until it declares the operation as failure')
@click.option('--clean', '-c', is_flag=True, default=True,
              help='Clean shutdown master')
@click.option('--no-wait', is_flag=True, default=False,
              help="Don't wait for complete master shutdown")
@click.pass_obj
def restart(obj, no_daemon, start_timeout, clean, no_wait):
    from buildbot.scripts.restart import restart
    command_cfg = {
        'basedir': obj['config_path'].parent.absolute(),
        'quiet': False,
        'nodaemon': no_daemon,
        'start_timeout': start_timeout,
        'clean': clean,
        'no-wait': no_wait
    }
    restart(command_cfg)


@ursabot.group()
@click.option('--docker-host', '-dh', default=None,
              help='Docker host url in form: tcp://127.0.0.1:2375')
@click.option('--docker-username', '-du', default=None,
              help='Username to authenticate dockerhub with')
@click.option('--docker-password', '-dp', default=None,
              help='Password to authenticate dockerhub with')
@click.option('--arch', '-a', default=None,
              help='Filter images by architecture')
@click.option('--os', '-o', default=None,
              help='Filter images by operating system')
@click.option('--tag', '-t', default=None,
              help='Filter images by operating system')
@click.option('--variant', '-v', default=None,
              help='Filter images by variant')
@click.option('--name', '-n', default=None, help='Filter images by name')
@click.pass_obj
def docker(obj, docker_host, docker_username, docker_password, **kwargs):
    """Subcommand to build docker images for the docker builders

    It loads the docker images defined
    """
    config = obj['config']
    if obj['verbose']:
        logging.getLogger('dockermap').setLevel(logging.INFO)

    client = DockerClientWrapper(docker_host)
    if docker_username is not None:
        client.login(username=docker_username, password=docker_password)

    filters = toolz.valfilter(lambda x: x is not None, kwargs)
    images = config.images.filter(**filters)

    obj['client'] = client
    obj['images'] = images


@docker.command('list')
@click.pass_obj
def list_images(obj):
    """List the docker images"""
    images = obj['images']
    for image in images:
        click.echo(image)


# TODO(kszucs): option to push to another organization
@docker.command()
@click.option('--push/--no-push', '-p', default=False,
              help='Push the built images')
@click.option('--no-cache/--cache', default=False,
              help='Do not use cache when building the images')
@click.pass_obj
def build(obj, push, no_cache):
    """Build docker images"""
    client = obj['client']
    images = obj['images']

    images.build(client=client, nocache=no_cache)
    if push:
        images.push(client=client)


@docker.command()
@click.option('--directory', '-d', default='images',
              help='Path to the directory where the images should be written')
@click.pass_obj
def write_dockerfiles(obj, directory):
    """Write the corresponding Dockerfile for the images"""
    images = obj['images']
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    for image in images:
        image.save_dockerfile(directory)
