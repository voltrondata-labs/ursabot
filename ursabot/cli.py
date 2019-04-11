import click
import logging

from dockermap.api import DockerClientWrapper

from .docker import arrow_images


logging.basicConfig()
logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose/--quiet', '-v', default=False, is_flag=True)
@click.pass_context
def ursabot(ctx, verbose):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

    if verbose:
        logger.setLevel(logging.INFO)


@ursabot.group()
@click.option('--docker-host', '-dh', default=None,
              help='Docker host url in form: tcp://127.0.0.1:2375')
@click.option('--docker-username', '-du', default=None,
              help='Username to authenticate dockerhub with')
@click.option('--docker-password', '-dp', default=None,
              help='Password to authenticate dockerhub with')
@click.pass_context
def docker(ctx, docker_host, docker_username, docker_password):
    if ctx.obj['verbose']:
        logging.getLogger('dockermap').setLevel(logging.INFO)

    client = DockerClientWrapper(docker_host)
    if docker_username is not None:
        client.login(username=docker_username, password=docker_password)

    ctx.obj['client'] = client


@docker.command()
@click.option('--push/--no-push', '-p', default=False,
              help='Push the built images')
@click.option('--architecture', '-a', default=None,
              help='Build docker images for this specifig architecture')
@click.option('--filter', '-f', default=None,
              help='Filter images by name')
@click.pass_context
def build(ctx, push, architecture, filter):
    if architecture is not None:
        imgs = [img for img in arrow_images if img.arch == architecture]
    else:
        imgs = arrow_images

    if filter is not None:
        imgs = [img for img in imgs if filter in img.fqn]

    client = ctx.obj['client']
    for img in imgs:
        click.echo(f'Building {img.fqn}')
        img.build(client=client)

    if push:
        for img in imgs:
            click.echo(f'Pushing {img.fqn}...')
            img.push(client=client)
