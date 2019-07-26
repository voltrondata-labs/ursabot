from pathlib import Path

from ursabot.docker import DockerImage, ADD, RUN, pip, worker_image_for


docker_assets = Path(__file__).parent.parent / 'docker'
ursabot_image = DockerImage(
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
worker_image = worker_image_for(ursabot_image)
