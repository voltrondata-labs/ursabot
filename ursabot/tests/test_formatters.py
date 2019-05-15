import textwrap
from pathlib import Path

from twisted.trial import unittest
from buildbot.process.results import FAILURE, SUCCESS
from buildbot.reporters import utils
from buildbot.test.fake import fakedb, fakemaster
from buildbot.test.util.misc import TestReactorMixin

from ursabot.formatters import (GitHubCommentFormatter,
                                BenchmarkCommentFormatter)
from ursabot.utils import ensure_deferred


class TestFormatter(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    def setupFormatter(self):
        raise NotImplementedError()

    def setupDb(self, results1, results2):
        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrkr'),
            fakedb.Buildset(id=98, results=results1, reason='testReason1'),
            fakedb.Buildset(id=99, results=results2, reason='testReason2'),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=80),
            fakedb.BuildRequest(id=12, buildsetid=99, builderid=80),
            fakedb.Build(id=20, number=0, builderid=80, buildrequestid=11,
                         workerid=13, masterid=92, results=results1),
            fakedb.Build(id=21, number=1, builderid=80, buildrequestid=12,
                         workerid=13, masterid=92, results=results1),
        ])
        for _id in (20, 21):
            self.db.insertTestData([
                fakedb.BuildProperty(
                    buildid=_id, name='workername', value='wrkr'),
                fakedb.BuildProperty(
                    buildid=_id, name='reason', value='because'),
            ])

    async def render(self, previous, current):
        self.setupDb(current, previous)

        buildset = await utils.getDetailsForBuildset(
            self.master,
            99,
            wantProperties=True,
            wantSteps=True,
            wantLogs=True
        )
        build = buildset['builds'][0]

        formatter = self.setupFormatter()

        return await formatter.render(build, master=self.master)


class TestGitHubCommentFormatter(TestFormatter):

    def setupFormatter(self):
        return GitHubCommentFormatter()

    @ensure_deferred
    async def test_message_success(self):
        content = await self.render(previous=SUCCESS, current=SUCCESS)
        assert content == 'success'

    @ensure_deferred
    async def test_message_failure(self):
        content = await self.render(previous=SUCCESS, current=FAILURE)
        assert content == 'failure'


class TestBenchmarkCommentFormatter(TestFormatter):

    def load_fixture(self, name):
        path = Path(__file__).parent / 'fixtures' / f'{name}'
        return path.read_text()

    def setupFormatter(self):
        return BenchmarkCommentFormatter()

    def setupDb(self, *args, **kwargs):
        super().setupDb(*args, **kwargs)

        result_log_content = self.load_fixture('archery-benchmark-diff.jsonl')

        self.db.insertTestData([
            fakedb.Step(id=50, buildid=21, number=0, name='compile'),
            fakedb.Step(id=51, buildid=21, number=1, name='benchmark'),
            fakedb.Log(id=60, stepid=51, name='result', slug='result',
                       type='s', num_lines=4),
            fakedb.LogChunk(logid=60, first_line=0, last_line=4, compressed=0,
                            content=result_log_content)
        ])

    @ensure_deferred
    async def test_message_success(self):
        expected = '''
        [unknown](http://localhost:8080/#builders/80/builds/1): test

        ```diff
          ============================  ===========  ===========  ===========
          benchmark                        baseline    contender       change
          ============================  ===========  ===========  ===========
          RegressionSumKernel/32768/50  1.92412e+10  1.92114e+10  -0.00155085
        - RegressionSumKernel/32768/1   2.48232e+10  2.47718e+10   0.00206818
          RegressionSumKernel/32768/10  2.19027e+10  2.19757e+10   0.00333234
        - RegressionSumKernel/32768/0   2.7685e+10   2.78212e+10  -0.00491813
          ============================  ===========  ===========  ===========
        ```
        '''
        content = await self.render(previous=SUCCESS, current=SUCCESS)
        assert content == textwrap.dedent(expected).strip()
