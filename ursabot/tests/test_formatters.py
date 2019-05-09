from twisted.trial import unittest

from buildbot.process.results import FAILURE, SUCCESS
from buildbot.reporters import utils
from buildbot.test.fake import fakedb, fakemaster
from buildbot.test.util.misc import TestReactorMixin


from ursabot.formatters import CommentFormatter
from ursabot.utils import ensure_deferred


class TestCommentFormatter(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)
        self.formatter = CommentFormatter()

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

    @ensure_deferred
    async def doOneTest(self, lastresults, results, mode='all'):
        self.setupDb(results, lastresults)
        details = await utils.getDetailsForBuildset(
            self.master, 99, wantProperties=True)

        build = details['builds'][0]
        buildset = details['buildset']
        result = await self.formatter.formatMessageForBuildResults(
            mode, 'Builder1', buildset, build, self.master, lastresults,
            ['him@bar', 'me@foo'])

        return result

    @ensure_deferred
    async def test_message_success(self):
        res = await self.doOneTest(SUCCESS, SUCCESS)
        self.assertEqual(res['type'], 'plain')
        self.assertTrue('subject' not in res)

    @ensure_deferred
    async def test_message_failure(self):
        res = await self.doOneTest(SUCCESS, FAILURE)
        self.assertIn(
            'The Buildbot has detected a failed build on builder', res['body']
        )

    @ensure_deferred
    async def test_message_failure_change(self):
        res = await self.doOneTest(SUCCESS, FAILURE, 'change')
        self.assertIn(
            'The Buildbot has detected a new failure on builder', res['body']
        )

    @ensure_deferred
    async def test_message_success_change(self):
        res = await self.doOneTest(FAILURE, SUCCESS, 'change')
        self.assertIn(
            'The Buildbot has detected a restored build on builder',
            res['body']
        )

    @ensure_deferred
    async def test_message_success_nochange(self):
        res = await self.doOneTest(SUCCESS, SUCCESS, 'change')
        self.assertIn(
            'The Buildbot has detected a passing build on builder',
            res['body']
        )

    @ensure_deferred
    async def test_message_failure_nochange(self):
        res = await self.doOneTest(FAILURE, FAILURE, 'change')
        self.assertIn(
            'The Buildbot has detected a failed build on builder',
            res['body']
        )
