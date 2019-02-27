import dask
import click
# import platform

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
    if architecture is not None:
        imgs = [img for (arch, img) in arrow_images if arch == architecture]
    else:
        imgs = [img for (_, img) in arrow_images]

    delimiter = '\n - '
    image_names = map(str, dask.compute(*imgs))
    click.echo('The following images are going to be built:{}'
               .format(delimiter + delimiter.join(image_names)))

    imgs = [img.build() for img in imgs]
    if push:
        imgs = [img.push(organization) for img in imgs]

    with ProgressBar():
        dask.compute(*imgs)
