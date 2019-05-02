import click
import logging
import toolz
from pathlib import Path

from dockermap.api import DockerClientWrapper

from .docker import arrow_images, ursabot_images


logging.basicConfig()
logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose/--quiet', '-v', default=False, is_flag=True)
@click.pass_context
def ursabot(ctx, verbose):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

    if verbose:
        logging.getLogger('ursabot').setLevel(logging.INFO)


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
@click.pass_context
def docker(ctx, docker_host, docker_username, docker_password, **kwargs):
    if ctx.obj['verbose']:
        logging.getLogger('dockermap').setLevel(logging.INFO)

    client = DockerClientWrapper(docker_host)
    if docker_username is not None:
        client.login(username=docker_username, password=docker_password)

    ctx.obj['client'] = client
    ctx.obj['filters'] = toolz.valfilter(lambda x: x is not None, kwargs)


@docker.command()
@click.argument('project')
@click.option('--push/--no-push', '-p', default=False,
              help='Push the built images')
@click.pass_context
def build(ctx, project, push):
    if project == 'arrow':
        images = arrow_images
    elif project == 'ursabot':
        images = ursabot_images
    else:
        raise ValueError(f'Uknown project: `{project}`')

    filters = ctx.obj['filters']
    images = images.filter(**filters)

    client = ctx.obj['client']
    images.build(client=client)

    if push:
        images.push(client=client)


@docker.command()
@click.argument('project')
@click.option('--directory', '-d', default='images',
              help='Path to the directory where the images should be written')
@click.pass_context
def write_dockerfiles(ctx, project, directory):
    if project == 'arrow':
        images = arrow_images
    elif project == 'ursabot':
        images = ursabot_images
    else:
        raise ValueError(f'Uknown project: `{project}`')

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    for image in images:
        image.save_dockerfile(directory)
