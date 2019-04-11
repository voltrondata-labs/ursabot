import pytest

from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin

from ursabot.steps import ShellCommand
from ursabot.utils import ensure_deferred


class BuildStepTestCase(unittest.TestCase, TestReactorMixin,
                        steps.BuildStepMixin, config.ConfigErrorsMixin):
    pass


class MyDockerCommand(ShellCommand):
    command = ['my-docker-binary']


class TestShellCommand(BuildStepTestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_constructor(self):
        # this checks that an exception is raised for invalid arguments
        msg = 'No command was provided'
        with pytest.raises(ValueError, match=msg):
            ShellCommand()

        msg = 'Command must be an instance of list or tuple'
        with pytest.raises(ValueError, match=msg):
            ShellCommand('something')

        cmd = ShellCommand(['echo', '1'])
        assert cmd.command == ('echo', '1')

        cmd = MyDockerCommand(['--help'])
        assert cmd.command == ('my-docker-binary', '--help')

    @ensure_deferred
    async def test_echo(self):
        self.setupStep(
            ShellCommand(command=['echo', '1'], workdir='build')
        )
        self.expectCommands(
            ExpectShell(workdir='build', command=['echo', '1']) +
            0
        )
        self.expectOutcome(result=SUCCESS)
        return await self.runStep()

    @ensure_deferred
    async def test_custom(self):
        self.setupStep(
            MyDockerCommand(['build', 'image-1', 'image-2'], workdir='build')
        )
        expected_cmd = ['my-docker-binary', 'build', 'image-1', 'image-2']
        self.expectCommands(
            ExpectShell(workdir='build', command=expected_cmd) +
            0
        )
        self.expectOutcome(result=SUCCESS)
        return await self.runStep()
