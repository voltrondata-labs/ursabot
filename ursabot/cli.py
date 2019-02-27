import click

from dask import delayed
from dask.diagnostics import ProgressBar

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
@click.option('--org', '-o', default='ursalab',
              help='DockerHub organization to push images to')
def build(push, org):
    @delayed
    def builder(img):
        id = img.build()
        # click.echo(f'{img} built with id: {id}')
        if push:
            img.push(org)
        return id

    results = map(builder, arrow_images)
    collect = delayed(list)

    with ProgressBar():
        collect(results).compute()
