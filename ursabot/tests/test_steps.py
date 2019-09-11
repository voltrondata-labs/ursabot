# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.
#
# This file contains function or sections of code that are marked as being
# derivative works of Buildbot. The above license only applies to code that
# is not marked as such.

import pytest
from pathlib import Path

from twisted.trial import unittest
from buildbot.plugins import util
from buildbot.process.results import SUCCESS
from buildbot.test.fake import logfile
from buildbot.process import remotetransfer, buildstep
from buildbot.test.util import config, steps
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.fake.remotecommand import (ExpectShell, Expect,
                                              ExpectRemoteRef)

from ursabot.steps import (ShellCommand, ResultLogMixin, SetPropertiesFromEnv,
                           SetPropertyFromCommand)
from ursabot.utils import ensure_deferred


fixtures = Path(__file__).parent / 'fixtures'


# the original FakeLogFile doesn't have an addContent which is used by the
# ResultLogMixin
class FakeLogFile(logfile.FakeLogFile):

    @ensure_deferred
    async def addContent(self, lines):
        return await self.addStdout(lines)


class BuildStepTestCase(unittest.TestCase, TestReactorMixin,
                        steps.BuildStepMixin, config.ConfigErrorsMixin):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, *args, **kwargs):
        super().setupStep(*args, **kwargs)

        @ensure_deferred
        async def addLog(name, type='s', logEncoding=None):
            log_ = FakeLogFile(name, self.step)
            self.step.logs[name] = log_
            return log_

        self.step.addLog = addLog


class MyDockerCommand(ShellCommand):
    command = ['my-docker-binary']


class TestShellCommand(BuildStepTestCase):

    def test_constructor(self):
        # this checks that an exception is raised for invalid arguments
        msg = 'No command was provided'
        with pytest.raises(ValueError, match=msg):
            ShellCommand()

        cmd = ShellCommand(command='something')
        assert cmd.command == util.FlattenList(['something'])

        cmd = ShellCommand(command='something', args=['arg1', 'arg2'])
        assert cmd.command == util.FlattenList(['something', ['arg1', 'arg2']])

        cmd = ShellCommand(command=['echo', '1'])
        assert cmd.command == util.FlattenList([('echo', '1')])

        cmd = MyDockerCommand(args=['--help'])
        assert cmd.command == util.FlattenList([
            ['my-docker-binary'], ['--help']
        ])

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


class TestSetPropertiesFromEnv(BuildStepTestCase):

    def test_simple(self):
        # License note:
        #    Copied from the original buildbot implementation with
        #    minor changes and additions.
        self.setupStep(
            SetPropertiesFromEnv({
                'prefix_one': 'one',
                'two': 'two',
                'three': 'three',
                'five': 'FIVE',
                'six': 'six'
            }, source='me')
        )
        self.worker.worker_environ = {
            'one': '1',
            'two': None,
            'six': '6',
            'FIVE': '555'
        }
        self.worker.worker_system = 'linux'
        self.properties.setProperty('four', 4, 'them')
        self.properties.setProperty('five', 5, 'them')
        self.properties.setProperty('six', 99, 'them')
        self.expectOutcome(result=SUCCESS,
                           state_string='Set')
        self.expectProperty('prefix_one', '1', source='me')
        self.expectNoProperty('two')
        self.expectNoProperty('three')
        self.expectProperty('four', 4, source='them')
        self.expectProperty('five', '555', source='me')
        self.expectProperty('six', '6', source='me')
        return self.runStep()


class TestSetPropertyFromCommand(BuildStepTestCase):

    @ensure_deferred
    async def test_run_property(self):
        self.setupStep(
            SetPropertyFromCommand(
                property='echoed',
                command='echo',
                args=['something'],
                workdir='build',
            )
        )
        self.expectCommands(
            ExpectShell(workdir='build', command=['echo', 'something']) +
            ExpectShell.log('stdio', stdout='something') +
            0
        )
        self.expectLogfile('stdio', 'something')
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('echoed', 'something')

        return await self.runStep()

    @ensure_deferred
    async def test_run_property_from_another_command(self):
        command = ShellCommand(command='echo', args=['something', 'else'])
        self.setupStep(
            SetPropertyFromCommand(
                property='echoed',
                command=command,
                workdir='build',
            )
        )
        self.expectCommands(
            ExpectShell(
                workdir='build',
                command=['echo', 'something', 'else']
            ) +
            ExpectShell.log('stdio', stdout='something else') +
            0
        )
        self.expectLogfile('stdio', 'something else')
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('echoed', 'something else')

        return await self.runStep()


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
        content = (fixtures / f'archery-benchmark-diff.jsonl').read_text()
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
