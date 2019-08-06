import os
from unittest.mock import Mock

import pytest
from twisted.trial import unittest
from buildbot.test.util.misc import TestReactorMixin
from buildbot.process.results import FAILURE, EXCEPTION

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


name = 'test'
repo = 'https://github.com/ursa-labs/ursabot'

images = worker_images_for([
    DockerImage('test', base='python:3.7', os='debian-9', arch='amd64')
])
workers = docker_workers_for(
    archs=['amd64'],
    masterFQDN=os.getenv('MASTER_FQDN')
)
echoer = DockerBuilder('echoer', image=images[0], workers=workers, steps=[
    ShellCommand(command='echo 1337', as_shell=True)
])
failer = DockerBuilder('failer', image=images[0], workers=workers, steps=[
    ShellCommand(command='unknown-command', as_shell=True)
])
builders = [echoer, failer]
schedulers = [
    AnyBranchScheduler(name='TestScheduler', builders=builders)
]

project = ProjectConfig(
    name=name,
    repo=repo,
    images=images,
    workers=workers,
    builders=builders,
    schedulers=schedulers
)
master = MasterConfig(title='Test', projects=[project])

sourcestamp = {
    'codebase': '',
    'project': project.name,
    'repository': project.repo,
    'branch': 'master',
    'revision': None
}


class TestMasterTestcase(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.timeout = 120
        images.build()
        self.setUpTestReactor()
        # import mock
        # stop = mock.create_autospec(self.reactor.stop)
        # self.patch(self.reactor, 'stop', stop)

    @pytest.mark.docker
    @pytest.mark.integration
    @ensure_deferred
    async def test_simple(self):
        async with _TestMaster(master, reactor=self.reactor) as m:
            result = await m.build(echoer.name, sourcestamp)

        assert result['complete'] is True
        assert result['results'] == 0
        assert result['bsid'] == 1

    @pytest.mark.docker
    @pytest.mark.integration
    @ensure_deferred
    async def test_attach_on_failure(self):
        worker = workers[0]
        worker.attach_interactive_shell = Mock()

        attach_on = {FAILURE, EXCEPTION}
        async with _TestMaster(master, reactor=self.reactor,
                               attach_on=attach_on) as m:
            await m.build(failer.name, sourcestamp)
            worker.attach_interactive_shell.assert_called_once()
