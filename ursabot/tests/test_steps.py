import pytest
from pathlib import Path

from twisted.trial import unittest
from buildbot.process.results import SUCCESS
from buildbot.process import remotetransfer, buildstep
from buildbot.test.util import config, steps
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.fake.remotecommand import (ExpectShell, Expect,
                                              ExpectRemoteRef)

from ursabot.steps import ShellCommand, ResultLogMixin
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

        msg = 'Args must be an instance of list or tuple'
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


fixture = Path(__file__).parent / 'fixtures' / f'archery-benchmark-diff.jsonl'


def upload_string(string):
    def behavior(command):
        writer = command.args['writer']
        writer.remote_write(string)
        writer.remote_close()
    return behavior


class MySuccessStep(buildstep.BuildStep):

    @ensure_deferred
    async def run(self):
        return SUCCESS


class MyStepWithResult(ResultLogMixin, MySuccessStep):
    pass


class TestResultLog(BuildStepTestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    @ensure_deferred
    async def test_result_log_from_file(self):
        content = fixture.read_text()
        self.setupStep(
            MyStepWithResult(workdir='build', result_file='result.json')
        )
        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc='result.json',
                workdir='build',
                blocksize=32 * 1024,
                maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            ) +
            Expect.behavior(upload_string(content)) +
            0
        )
        self.expectLogfile('result', content)
        self.expectOutcome(result=SUCCESS)

        return await self.runStep()
