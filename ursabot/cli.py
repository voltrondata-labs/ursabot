import dask
import click
# import platform

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
@click.option('--organization', '-o', default='ursalab',
              help='DockerHub organization to push images to')
@click.option('--architecture', '-a', default=None,  # TODO(kszucs) detect
              help='Build docker images for this specifig architecture')
def build(push, organization, architecture):
    @delayed
    def builder(img):
        id = img.build()
        # click.echo(f'{img} built with id: {id}')
        if push:
            img.push(organization)
        return id

    if architecture is not None:
        imgs = [img for (arch, img) in arrow_images if arch == architecture]
    else:
        imgs = [img for (_, img) in arrow_images]

    delimiter = '\n - '
    image_names = map(str, dask.compute(*imgs))
    click.echo('The following images are going to be built:{}'
               .format(delimiter + delimiter.join(image_names)))

    results = map(builder, imgs)
    with ProgressBar():
        dask.compute(*results)
