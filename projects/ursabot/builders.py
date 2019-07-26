from buildbot.plugins import util
from ursabot.builders import DockerBuilder
from ursabot.steps import ShellCommand, PyTest, Pip, GitHub

from images import worker_image


class UrsabotTest(DockerBuilder):
    tags = ['ursabot']
    steps = [
        GitHub(
            name='Clone Ursabot',
            repourl=util.Property('repository'),
            mode='full'
        ),
        Pip(['install', '-e', '.']),
        PyTest(args=['-m', 'not docker', 'ursabot']),
        ShellCommand(
            command=['flake8', 'ursabot'],
            name='Flake8'
        ),
        ShellCommand(
            command=['buildbot', 'checkconfig', '.'],
            env={'URSABOT_ENV': 'test'},
            name='Checkconfig'
        )
    ]
    images = [worker_image]
