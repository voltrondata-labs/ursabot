import textwrap
import traceback
from pathlib import Path

from twisted.trial import unittest
from buildbot.process.results import FAILURE, SUCCESS, EXCEPTION
from buildbot.reporters import utils
from buildbot.test.fake import fakedb, fakemaster
from buildbot.test.util.misc import TestReactorMixin

from ursabot.formatters import (Formatter, MarkdownFormatter,
                                BenchmarkCommentFormatter)
from ursabot.utils import ensure_deferred


class TestFormatterBase(TestReactorMixin, unittest.TestCase):

    BUILD_URL = 'http://localhost:8080/#builders/80/builds/1'
    REVISION = '989ec01feb96c2563f39b1751bcc29822c8db4b8'

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
                fakedb.BuildProperty(buildid=_id, name='buildername',
                                     value='Builder1'),
                fakedb.BuildProperty(buildid=_id, name='workername',
                                     value='wrkr'),
                fakedb.BuildProperty(buildid=_id, name='revision',
                                     value=self.REVISION),
                fakedb.BuildProperty(buildid=_id, name='reason',
                                     value='because')
            ])

    async def render(self, previous, current, buildsetid=99, complete=True,
                     **kwargs):
        self.setupDb(current, previous, **kwargs)

        buildset = await utils.getDetailsForBuildset(
            self.master,
            buildsetid,
            wantProperties=True,
            wantSteps=True,
            wantLogs=True
        )
        build = buildset['builds'][0]
        build['complete'] = complete

        formatter = self.setupFormatter()

        return await formatter.render(build, master=self.master)


class TestFormatter(TestFormatterBase):

    def setupFormatter(self):
        return Formatter()

    @ensure_deferred
    async def test_message_started(self):
        content = await self.render(previous=SUCCESS, current=-1,
                                    complete=False)
        assert content == 'Build started.'

    @ensure_deferred
    async def test_message_success(self):
        content = await self.render(previous=SUCCESS, current=SUCCESS)
        assert content == 'Build succeeded.'

    @ensure_deferred
    async def test_message_failure(self):
        content = await self.render(previous=SUCCESS, current=FAILURE)
        assert content == 'Build failed.'


class TestMarkdownFormatter(TestFormatterBase):

    def setupDb(self, current, previous, log1=None, log2=None):
        super().setupDb(current, previous)

        self.db.insertTestData([
            fakedb.Step(id=50, buildid=21, number=0, name='Compile'),
            fakedb.Step(id=51, buildid=21, number=1, name='Benchmark',
                        results=current, state_string='/bin/run-benchmark'),
            fakedb.Step(id=52, buildid=20, number=0, name='Compile'),
            fakedb.Step(id=53, buildid=20, number=1, name='Benchmark',
                        results=current, state_string='/bin/run-benchmark')
        ])

        if current == SUCCESS:
            self.db.insertTestData([
                fakedb.Log(id=60, stepid=51, name='stdio', slug='stdio',
                           type='s', num_lines=len(log1)),
                fakedb.Log(id=61, stepid=53, name='stdio', slug='stdio',
                           type='s', num_lines=len(log2)),
                fakedb.LogChunk(logid=60, first_line=0, last_line=4,
                                compressed=0, content='\n'.join(log1)),
                fakedb.LogChunk(logid=61, first_line=0, last_line=6,
                                compressed=0, content='\n'.join(log2))
            ])
        elif current == FAILURE:
            self.db.insertTestData([
                fakedb.Log(id=60, stepid=51, name='stdio', slug='stdio',
                           type='s', num_lines=len(log1)),
                fakedb.Log(id=61, stepid=53, name='stdio', slug='stdio',
                           type='s', num_lines=len(log2)),
                fakedb.LogChunk(logid=60, first_line=0, last_line=4,
                                compressed=0, content='\n'.join(log1)),
                fakedb.LogChunk(logid=61, first_line=0, last_line=6,
                                compressed=0, content='\n'.join(log2))
            ])
        elif current == EXCEPTION:
            self.db.insertTestData([
                fakedb.Log(id=60, stepid=51, name='err.text', slug='err_text',
                           type='t', num_lines=len(log1)),
                fakedb.Log(id=61, stepid=53, name='err.text', slug='err_text',
                           type='t', num_lines=len(log2)),
                fakedb.LogChunk(logid=60, first_line=0, last_line=4,
                                compressed=0, content='\n'.join(log1)),
                fakedb.LogChunk(logid=61, first_line=0, last_line=6,
                                compressed=0, content='\n'.join(log2))
            ])

    def setupFormatter(self):
        return MarkdownFormatter()

    @ensure_deferred
    async def test_started(self):
        expected = f'''
        [Builder1]({self.BUILD_URL}) builder is started.

        Revision: {self.REVISION}
        '''
        content = await self.render(previous=SUCCESS, current=-1,
                                    complete=False)
        assert content == textwrap.dedent(expected).strip()

    @ensure_deferred
    async def test_success(self):
        expected = f'''
        [Builder1]({self.BUILD_URL}) builder has been succeeded.

        Revision: {self.REVISION}
        '''
        log1 = ('hline1', 'hline2', 'sline3')
        log2 = ('hline1', 'sline2', 'sline3', 'hline7')
        content = await self.render(previous=SUCCESS, current=SUCCESS,
                                    log1=log1, log2=log2)
        assert content == textwrap.dedent(expected).strip()

    @ensure_deferred
    async def test_failure(self):
        BUILD_URL = self.BUILD_URL
        log1 = ('hline1', 'hline2', 'sline3', 'eline4', 'eline5')
        log2 = ('hline1', 'eline2', 'eline3', 'sline4', 'eline5', 'eline6')

        expected = f'''
        [Builder1]({BUILD_URL}) builder has been failed.

        Revision: {self.REVISION}

        Benchmark: `/bin/run-benchmark` step's stderr:
        ```
        line4
        line5
        ```
        '''
        content = await self.render(buildsetid=99, previous=SUCCESS,
                                    current=FAILURE, log1=log1, log2=log2)
        assert content == textwrap.dedent(expected).strip()

        BUILD_URL = 'http://localhost:8080/#builders/80/builds/0'
        expected = f'''
        [Builder1]({BUILD_URL}) builder has been failed.

        Revision: {self.REVISION}

        Benchmark: `/bin/run-benchmark` step's stderr:
        ```
        line2
        line3
        line5
        line6
        ```
        '''
        content = await self.render(buildsetid=98, previous=SUCCESS,
                                    current=FAILURE, log1=log1, log2=log2)
        assert content == textwrap.dedent(expected).strip()

    @ensure_deferred
    async def test_exception(self):
        try:
            raise ValueError()
        except Exception:
            log1 = traceback.format_exc().strip()
        try:
            raise TypeError()
        except Exception:
            log2 = traceback.format_exc().strip()

        expected = f'''
        [Builder1]({self.BUILD_URL}) builder has been failed with an exception.

        Revision: {self.REVISION}

        Benchmark: `/bin/run-benchmark` step's traceback:
        ```pycon
        {{log1}}
        ```
        '''
        content = await self.render(buildsetid=99, previous=SUCCESS,
                                    current=EXCEPTION, log1=log1.splitlines(),
                                    log2=log2.splitlines())
        assert content == textwrap.dedent(expected).strip().format(log1=log1)


class TestBenchmarkCommentFormatter(TestFormatterBase):

    def load_fixture(self, name):
        path = Path(__file__).parent / 'fixtures' / f'{name}'
        return path.read_text()

    def setupFormatter(self):
        return BenchmarkCommentFormatter()

    def setupDb(self, current, previous):
        super().setupDb(current, previous)

        log1 = self.load_fixture('archery-benchmark-diff.jsonl')
        log2 = self.load_fixture('archery-benchmark-diff-empty-lines.jsonl')

        self.db.insertTestData([
            fakedb.Step(id=50, buildid=21, number=0, name='compile'),
            fakedb.Step(id=51, buildid=21, number=1, name='benchmark',
                        results=current),
            fakedb.Step(id=52, buildid=20, number=0, name='compile'),
            fakedb.Step(id=53, buildid=20, number=1, name='benchmark',
                        results=current),
            fakedb.Log(id=60, stepid=51, name='result', slug='result',
                       type='t', num_lines=4),
            fakedb.Log(id=61, stepid=53, name='result', slug='result',
                       type='t', num_lines=6),
            fakedb.LogChunk(logid=60, first_line=0, last_line=4, compressed=0,
                            content=log1),
            fakedb.LogChunk(logid=61, first_line=0, last_line=6, compressed=0,
                            content=log2)
        ])

    @ensure_deferred
    async def test_failure(self):
        expected = f'''
        [Builder1]({self.BUILD_URL}) builder has been failed.

        Revision: {self.REVISION}
        '''
        content = await self.render(previous=SUCCESS, current=FAILURE)
        assert content == textwrap.dedent(expected).strip()

    @ensure_deferred
    async def test_success(self):
        expected = f'''
        [Builder1]({self.BUILD_URL}) builder has been succeeded.

        Revision: {self.REVISION}

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
        content = await self.render(previous=SUCCESS, current=SUCCESS,
                                    buildsetid=99)
        assert content == textwrap.dedent(expected).strip()

    @ensure_deferred
    async def test_empty_jsonlines(self):
        BUILD_URL = 'http://localhost:8080/#builders/80/builds/0'
        expected = f'''
        [Builder1]({BUILD_URL}) builder has been succeeded.

        Revision: {self.REVISION}

        ```diff
          ============================  ===========  ===========  ==========
          benchmark                        baseline    contender      change
          ============================  ===========  ===========  ==========
          RegressionSumKernel/32768/10  1.32654e+10  1.33275e+10  0.00467565
          RegressionSumKernel/32768/1   1.51819e+10  1.522e+10    0.00251084
          RegressionSumKernel/32768/50  1.14718e+10  1.15116e+10  0.00346736
          RegressionSumKernel/32768/0   1.8317e+10   1.85027e+10  0.010141
          ============================  ===========  ===========  ==========
        ```
        '''
        content = await self.render(previous=SUCCESS, current=SUCCESS,
                                    buildsetid=98)
        assert content == textwrap.dedent(expected).strip()
