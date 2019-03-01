import click
# import dask
# import platform
# from dask.diagnostics import ProgressBar

from .docker import arrow_images


@click.group()
def ursabot():
    pass


@ursabot.group()
def docker():
    pass


@docker.command()
@click.option('--push/--no-push', '-p', default=False,
              help='Push the built images')
@click.option('--architecture', '-a', default=None,
              help='Build docker images for this specifig architecture')
@click.option('--filter', '-f', default=None,
              help='Filter images by name')
def build(push, architecture, filter):
    if architecture is not None:
        imgs = [img for img in arrow_images if img.arch == architecture]
    else:
        imgs = arrow_images

    if filter is not None:
        imgs = [img for img in imgs if filter in img.fqn]

    for img in imgs:
        click.echo(f'Building {img.fqn}')
        img.build()

    if push:
        for img in imgs:
            click.echo(f'Pushing {img.fqn}...')
            img.push()

    # Build eagerly for now
    # with ProgressBar():
    #     dask.compute(*imgs)
