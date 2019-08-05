import os

import pytest
from twisted.trial import unittest
from buildbot.test.util.misc import TestReactorMixin

from dotenv import load_dotenv
from ursabot.master import TestMaster as _TestMaster
from ursabot.utils import ensure_deferred
from ursabot.configs import MasterConfig, ProjectConfig
from ursabot.builders import DockerBuilder
from ursabot.schedulers import AnyBranchScheduler
from ursabot.workers import docker_workers_for
from ursabot.docker import DockerImage, worker_images_for
from ursabot.steps import ShellCommand


# loading MASTER_FQDN from .env file, required for OSX
load_dotenv()


class Echoer(DockerBuilder):
    steps = [
        ShellCommand(command='echo 1337', as_shell=True)
    ]


name = 'test'
repo = 'https://github.com/ursa-labs/ursabot'

testimg = DockerImage('test', base='python:3.7', os='debian-9', arch='amd64')
images = worker_images_for(images=[testimg])
workers = docker_workers_for(archs=['amd64'],
                             masterFQDN=os.getenv('MASTER_FQDN'))
builders = Echoer.builders_for(workers, images=images)

schedulers = [
    AnyBranchScheduler(
        name='TestScheduler',
        builders=builders
    )
]

project = ProjectConfig(
    name=name,
    repo=repo,
    workers=workers,
    builders=builders,
    schedulers=schedulers
)


class TestMasterTestcase(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.timeout = 120
        images.build()
        self.setUpTestReactor()

    # TODO(kszucs): test for attaching to a failing build with mocking
    #               worker.attach_interactive_shell

    @pytest.mark.docker
    @pytest.mark.integration
    @ensure_deferred
    async def test_simple(self):
        config = MasterConfig(
            title='Test',
            worker_port=9888,  # randomize
            projects=[project]
        )
        sourcestamp = {
            'codebase': '',
            'project': project.name,
            'repository': project.repo,
            'branch': 'master',
            'revision': None
        }

        async with _TestMaster(config, reactor=self.reactor) as master:
            result = await master.build(builders[0].name, sourcestamp)

        assert result['complete'] is True
        assert result['results'] == 0
        assert result['bsid'] == 1
