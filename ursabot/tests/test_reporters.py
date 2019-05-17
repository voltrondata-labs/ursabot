from datetime import datetime
from dateutil.tz import tzutc

import pytest
from twisted.trial import unittest
from buildbot.config import ConfigErrors
from buildbot.process.results import SUCCESS, FAILURE, EXCEPTION, Results
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.test.unit import test_reporter_github as github
from buildbot.test.unit import test_reporter_zulip as zulip

from ursabot.reporters import (HttpReporterBase, ZulipStatusPush,
                               GitHubStatusPush, GitHubReviewPush,
                               GitHubCommentPush)
from ursabot.utils import ensure_deferred


class TestHttpReporterBase(unittest.TestCase, TestReactorMixin,
                           ReporterTestMixin):

    @ensure_deferred
    async def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True)

    def tearDown(self):
        if self.master.running:
            return self.master.stopService()

    async def setService(self, **kwargs):
        self.sp = HttpReporterBase(name='test', **kwargs)
        await self.sp.setServiceParent(self.master)
        await self.master.startService()
        return self.sp

    async def setupBuildResults(self, build_results, complete=True):
        self.insertTestData([build_results], build_results)
        build = await self.master.data.get(('builds', 20))
        build['complete'] = complete  # complete flag is not handled...
        return build

    async def check_report_on(self, whitelist, blacklist, expected):
        reporter = await self.setService(report_on=whitelist,
                                         dont_report_on=blacklist)

        # it is not clear how does buildbot handle started state, at least the
        # test suite doesn't handle the complete flag properly, so set result
        # to -1 for incomplete build
        build = await self.setupBuildResults(-1, complete=False)
        assert reporter.filterBuilds(build) is expected['started']

        for result in Results:
            build = await self.setupBuildResults(Results.index(result),
                                                 complete=True)
            assert reporter.filterBuilds(build) is expected[result]

    @ensure_deferred
    async def test_report_on_everything_by_default(self):
        await self.check_report_on(
            whitelist=None,
            blacklist=None,
            expected={
                'started': True,
                'success': True,
                'warnings': True,
                'failure': True,
                'skipped': True,
                'exception': True,
                'retry': True,
                'cancelled': True
            }
        )

    @ensure_deferred
    async def test_report_on_whitelist(self):
        await self.check_report_on(
            whitelist={'failure', 'exception'},
            blacklist=None,
            expected={
                'started': False,
                'success': False,
                'warnings': False,
                'failure': True,
                'skipped': False,
                'exception': True,
                'retry': False,
                'cancelled': False
            }
        )

    @ensure_deferred
    async def test_report_on_blacklist(self):
        await self.check_report_on(
            whitelist=None,
            blacklist={'failure', 'retry', 'started'},
            expected={
                'started': False,
                'success': True,
                'warnings': True,
                'failure': False,
                'skipped': True,
                'exception': True,
                'retry': False,
                'cancelled': True
            }
        )

    @ensure_deferred
    async def test_report_on_both_whitelist_and_blacklist(self):
        with pytest.raises(ConfigErrors):
            await self.check_report_on(
                whitelist={'exception', 'started'},
                blacklist={'failure', 'retry'},
                expected={}
            )


class TestZulipStatusPush(zulip.TestZulipStatusPush):

    @ensure_deferred
    async def setupZulipStatusPush(self, endpoint='http://example.com',
                                   token='123', stream=None, **kwargs):
        # setup our own implementation
        self.sp = ZulipStatusPush(endpoint=endpoint, token=token,
                                  stream=stream, **kwargs)
        self._http = await httpclientservice.HTTPClientService.getFakeService(
            self.master, self, endpoint, debug=None, verify=None)
        await self.sp.setServiceParent(self.master)
        await self.master.startService()

    @ensure_deferred
    async def setupBuildResults(self, result=SUCCESS):
        self.insertTestData([result], result)
        return await self.master.data.get(('builds', 20))

    @ensure_deferred
    async def test_dont_report_build_started(self):
        await self.setupZulipStatusPush(stream='xyz',
                                        dont_report_on={'started'})
        build = await self.setupBuildResults()
        build['started_at'] = datetime(2019, 4, 1, 23, 38, 43, 154354,
                                       tzinfo=tzutc())
        self.sp.buildStarted(('build', 20, 'new'), build)

    @ensure_deferred
    async def test_only_report_on_failure(self):
        await self.setupZulipStatusPush(stream='xyz', report_on={'failure'})
        build = await self.setupBuildResults(SUCCESS)
        build['complete'] = True
        build['complete_at'] = datetime(2019, 4, 1, 23, 38, 43, 154354,
                                        tzinfo=tzutc())
        self._http.expect(
            'post',
            '/api/v1/external/buildbot?api_key=123&stream=xyz',
            json={
                'event': 'finished',
                'buildid': 20,
                'buildername': 'Builder0',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'project': 'testProject',
                'timestamp': 1554161923,
                'results': FAILURE
            })
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        self.sp.buildFinished(('build', 20, 'finished'), build)


class TestGitHubStatusPush(github.TestGitHubStatusPush):

    def setService(self):
        # test or own implementation
        self.sp = GitHubStatusPush(token='XXYYZZ')
        return self.sp


class TestGitHubStatusPushURL(github.TestGitHubStatusPushURL):
    # project must be in the form <owner>/<project>
    TEST_PROJECT = 'buildbot'
    TEST_REPO = 'https://github.com/buildbot1/buildbot1.git'

    def setService(self):
        # test or own implementation
        self.sp = GitHubStatusPush(token='XXYYZZ')
        return self.sp


class TestGitHubReviewPush(TestGitHubStatusPush):

    def setService(self):
        self.sp = GitHubReviewPush(token='XXYYZZ')
        return self.sp

    @ensure_deferred
    async def test_basic(self):
        build = await self.setupBuildResults(SUCCESS)

        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': '',
                'commit_id': 'd34db33fd43db33f'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'APPROVE',
                'commit_id': 'd34db33fd43db33f'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'REQUEST_CHANGES',
                'commit_id': 'd34db33fd43db33f'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'REQUEST_CHANGES',
                'commit_id': 'd34db33fd43db33f'
            }
        )

        build['complete'] = False
        self.sp.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = EXCEPTION
        self.sp.buildFinished(('build', 20, 'finished'), build)


class TestGitHubCommentPush(github.TestGitHubCommentPush):

    def setService(self):
        # test or own implementation
        self.sp = GitHubCommentPush(token='XXYYZZ')
        return self.sp

    @ensure_deferred
    async def test_basic(self):
        build = await self.setupBuildResults(SUCCESS)

        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'success'})
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'failure'})

        build['complete'] = False
        self.sp.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        self.sp.buildFinished(('build', 20, 'finished'), build)
