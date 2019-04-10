import click
import logging
# import dask
# import platform
# from dask.diagnostics import ProgressBar

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
@click.pass_context
def docker(ctx):
    if ctx.obj['verbose']:
        logging.getLogger('dockermap').setLevel(logging.INFO)


@docker.command()
@click.option('--client', '-c', default=None,
              help='Docker client url in form: tcp://127.0.0.1:2375')
@click.option('--push/--no-push', '-p', default=False,
              help='Push the built images')
@click.option('--architecture', '-a', default=None,
              help='Build docker images for this specifig architecture')
@click.option('--filter', '-f', default=None,
              help='Filter images by name')
def build(client, push, architecture, filter):
    if architecture is not None:
        imgs = [img for img in arrow_images if img.arch == architecture]
    else:
        imgs = arrow_images

    if filter is not None:
        imgs = [img for img in imgs if filter in img.fqn]

    for img in imgs:
        click.echo(f'Building {img.fqn}')
        img.build(client=client)

    if push:
        for img in imgs:
            click.echo(f'Pushing {img.fqn}...')
            img.push(client=client)

    # Build eagerly for now
    # with ProgressBar():
    #     dask.compute(*imgs)
