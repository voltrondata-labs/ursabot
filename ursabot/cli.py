# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import io
import sys
import logging
import toolz
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr

import click
from dockermap.api import DockerClientWrapper
from twisted.internet import reactor, defer
from twisted.python.log import PythonLoggingObserver
from buildbot.util.logger import Logger
from buildbot.config import ConfigErrors
from buildbot.master import BuildMaster
from buildbot.process.results import Results, SUCCESS, WARNINGS

from .configs import Config, MasterConfig, InMemoryLoader
from .utils import ensure_deferred


logging.basicConfig()
logger = logging.getLogger(__name__)
logger_ = Logger()  # twisted's logger


@click.group()
@click.option('--verbose/--quiet', '-v', default=False, is_flag=True)
@click.option('--config-path', '-c', default='master.cfg',
              help='Configuration file path')
@click.option('--config-variable', '-cv', default='master',
              help='Variable name in the configuration which must be an '
                   'instance of MasterConfig')
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

    if not isinstance(config, MasterConfig):
        raise click.UsageError(
            f'The loaded variable `{config_variable}` from `{config_path}` '
            f'has type `{type(config)}` whereas it needs to be an instance of '
            f'MasterConfig'
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
        config.as_buildbot(source=config_path.name)
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

    config = obj['config']
    config_path = obj['config_path']
    basedir = config_path.parent.absolute()

    command_cfg = {'basedir': basedir, 'quiet': False}
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
def docker_list_images(obj):
    """List the docker images"""
    images = obj['images']
    for image in images:
        click.echo(image)


# TODO(kszucs): option to push to another organization
@docker.command('build')
@click.option('--push/--no-push', '-p', default=False,
              help='Push the built images')
@click.option('--no-cache/--cache', default=False,
              help='Do not use cache when building the images')
@click.pass_obj
def docker_image_build(obj, push, no_cache):
    """Build docker images"""
    client = obj['client']
    images = obj['images']

    images.build(client=client, nocache=no_cache)
    if push:
        images.push(client=client)


@docker.command('write-dockerfiles')
@click.option('--directory', '-d', default='images',
              help='Path to the directory where the images should be written')
@click.pass_obj
def docker_write_dockerfiles(obj, directory):
    """Write the corresponding Dockerfile for the images"""
    images = obj['images']
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    for image in images:
        image.save_dockerfile(directory)


@ursabot.group()
@click.option('--project', '-p', default=None,
              help='If the master has multiple projects configured, one must '
                   'be selected.')
@click.pass_obj
def project(obj, project):
    # retrieve the master's and the selected project's configurations
    try:
        obj['project'] = obj['config'].project(name=project)
    except Exception as e:
        raise click.UsageError(str(e))


class CLITestLoader(InMemoryLoader):

    def loadConfig(self):
        return self.config.as_clitest('CLI')


@ensure_deferred
async def _do_local_build(config, builder_name, sourcestamp, properties,
                          log_handler, result_handler):
    basedir = Path(__file__).parent.absolute()
    loader = CLITestLoader(config)
    master = BuildMaster(str(basedir), reactor=reactor, config_loader=loader)

    offset = 0
    buildset = defer.Deferred()
    buildset_id = None  # set later, but a callback uses it

    def on_buildset_complete(key, bs):
        assert bs['bsid'] == buildset_id
        buildset.callback(bs)

    def on_log_creation(key, log):
        nonlocal offset
        offset = 0

    @ensure_deferred
    async def on_log_append(key, log):
        nonlocal offset
        contents = await master.data.get(('logs', log['logid'], 'contents'))
        newlines = contents['content'][offset:]
        offset += len(newlines)
        log_handler(newlines.splitlines())

    # start the master and its dependent services
    await master.startService()

    consumers = [
        await master.mq.startConsuming(
            callback=on_log_creation,
            filter=('logs', None, 'new')
        ),
        await master.mq.startConsuming(
            callback=on_log_append,
            filter=('logs', None, 'append')
        ),
        await master.mq.startConsuming(
            callback=on_buildset_complete,
            filter=('buildsets', None, 'complete')
        )
    ]

    try:
        builder_id = await master.data.updates.findBuilderId(builder_name)
        buildset_id, _ = await master.data.updates.addBuildset(
            waited_for=False,
            builderids=[builder_id],
            properties={k: (v, 'CLI') for k, v in properties.items()},
            sourcestamps=[sourcestamp]
        )
        result_handler(await buildset)
    finally:
        # stop all the running services then shut down the reactor
        for c in consumers:
            c.stopConsuming()
        await master.stopService()
        reactor.stop()


def _handle_stdio_log(newlines):
    # 'o': 'stdout',
    # 'e': 'stderr',
    # 'h': 'header'
    for l in newlines:
        if l.startswith('h'):
            click.echo(click.style(l[1:], fg='blue'))
        elif l.startswith('e'):
            click.echo(click.style(l[1:], fg='red'))
        else:
            click.echo(l[1:])


def _handle_buildset_result(buildset):
    if not buildset['complete']:
        raise click.ClickException('Build has not completed')

    # 'results' refers to the final state of the build
    if buildset['results'] in (SUCCESS, WARNINGS):
        click.echo(click.style('Build successful!', fg='green'))
    else:
        state = Results[buildset['results']]
        raise click.ClickException(f'Build has failed with state {state}')


# TODO(kszucs): mountable source directory (which kicks off the source steps)
@project.command('build')
@click.argument('builder_name', nargs=1)
@click.option('--repo', '-r', default=None,
              help='Repository to clone, defaults to the Project\'s repo.')
@click.option('--branch', '-b', default='master', help='Branch to clone')
@click.option('--commit', '-c', default=None, help='Commit to clone')
@click.option('--pull-request', '-pr', type=int, default=None,
              help='Github pull request to clone, owerwrites the branch '
                   'option')
@click.option('--property', '-p', 'properties', multiple=True,
              help='Arbitrary properties passed to the builds. It must be '
                   'passed in form `name=value`')
@click.pass_obj
def project_build(obj, builder_name, repo, branch, commit, pull_request,
                  properties):
    # force twisted logger to use the cli module's python logger
    observer = PythonLoggingObserver(loggerName=logger.name)
    observer.start()

    config, project = obj['config'], obj['project']

    # construct the sourcestamp which will trigger the builders
    if pull_request is not None:
        branch = f'refs/pull/{pull_request}/merge'
    sourcestamp = {
        'codebase': '',
        'repository': repo or project.repo,
        'branch': branch,
        'revision': commit,
        'project': project.name
    }
    properties = dict(p.split('=') for p in properties)

    # spin up a lightweight master with in-memory database and trigger the
    # requested builders
    reactor.callWhenRunning(
        _do_local_build,
        config=config,
        builder_name=builder_name,
        sourcestamp=sourcestamp,
        properties=properties,
        log_handler=_handle_stdio_log,
        result_handler=_handle_buildset_result,
    )
    reactor.run()


@ursabot.command('desc')
@click.pass_obj
def master_desc(obj):
    """Describe master configuration"""

    def ul(values):
        return '\n'.join(f' - {v}' for v in values)

    config = obj['config']

    click.echo('Docker images:')
    click.echo(ul(config.images))
    click.echo()
    click.echo('Workers:')
    click.echo(ul(config.workers))
    click.echo()
    click.echo('Builders:')
    click.echo(ul(config.builders))
    click.echo()


@project.command('desc')
@click.pass_obj
def project_desc(obj):
    """Describe project configuration"""
    def ul(values):
        return '\n'.join(f' - {v}' for v in values)

    project = obj['project']
    click.echo(f'Name: {project.name}')
    click.echo(f'Repo: {project.repo}')
    click.echo()
    click.echo('Docker images:')
    click.echo(ul(project.images))
    click.echo()
    click.echo('Workers:')
    click.echo(ul(project.workers))
    click.echo()
    click.echo('Builders:')
    click.echo(ul(project.builders))
    click.echo()
