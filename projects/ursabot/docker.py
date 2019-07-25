from pathlib import Path

from ursabot.docker import ImageCollection, DockerImage, ADD, RUN, pip


# Note the python has a special treatment, because buildbot requires it.
# So all of the following images must have a python interpreter and pip
# pre-installed.
images = ImageCollection()


docker_assets = Path()  # TODO

# URSABOT
ursabot = DockerImage(
    name='ursabot',
    base='python:3.7',
    arch='amd64',
    os='debian-9',
    org='ursalab',
    title='Ursabot Python 3.7',
    steps=[
        ADD(docker_assets / 'requirements-ursabot.txt'),
        RUN(pip(files=['requirements-ursabot.txt']))
    ]
)

images.append(ursabot)
