from datetime import datetime
from dateutil.tz import tzutc

import pytest
from mock import Mock
from twisted.trial import unittest
from buildbot import config
from buildbot.config import ConfigErrors
from buildbot.process.results import SUCCESS, FAILURE, EXCEPTION, Results
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.test.unit import test_reporter_github as github
from buildbot.test.unit import test_reporter_zulip as zulip

from ursabot.reporters import (HttpStatusPush, ZulipStatusPush,
                               GitHubStatusPush, GitHubReviewPush,
                               GitHubCommentPush)
from ursabot.formatters import Formatter
from ursabot.utils import ensure_deferred


class TestHttpStatusPush(unittest.TestCase, TestReactorMixin,
                         ReporterTestMixin):

    @ensure_deferred
    async def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True)

    def tearDown(self):
        if self.master.running:
            return self.master.stopService()

    async def setService(self, **kwargs):
        self.sp = HttpStatusPush(name='test', baseURL='http://example.com',
                                 **kwargs)
        await self.sp.setServiceParent(self.master)
        await self.master.startService()
        return self.sp

    async def setupBuildResults(self, build_results, complete=True):
        self.insertTestData([build_results], build_results)
        build = await self.master.data.get(('builds', 20))
        builder = await self.master.data.get(('builders', build['builderid']))
        build['builder'] = builder
        build['complete'] = complete
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

    @ensure_deferred
    async def test_filter_builds_with_undefined_builders(self):
        reporter = await self.setService(builders=None)
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert reporter.filterBuilds(build)

    @ensure_deferred
    async def test_filter_builds_with_empty_list_of_builders(self):
        reporter = await self.setService(builders=[])
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert not reporter.filterBuilds(build)

    @ensure_deferred
    async def test_filter_builds_should_report_on_builder(self):
        reporter = await self.setService(builders=['Builder0'])
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert reporter.filterBuilds(build)

    @ensure_deferred
    async def test_filter_builds_should_not_report_on_builder(self):
        reporter = await self.setService(builders=['Builder1'])
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert not reporter.filterBuilds(build)


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
    async def test_filter_builders(self):
        await self.setupZulipStatusPush(stream='xyz', builders=['Builder1'])
        build = await self.setupBuildResults(SUCCESS)
        self.sp.buildStarted(('build', 20, 'new'), build)

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
            }
        )
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        self.sp.buildFinished(('build', 20, 'finished'), build)


class DumbFormatterForStatusPush(Formatter):
    """Formatter to conform the original test case"""

    layout = "{{ message }}"

    def render_success(self, build, master):
        return dict(message='Build done.')

    def render_warnings(self, build, master):
        return dict(message='Build done.')

    def render_skipped(self, build, master):
        return dict(message='Build done.')

    def render_exception(self, build, master):
        return dict(message='Build done.')

    def render_cancelled(self, build, master):
        return dict(message='Build done.')

    def render_failure(self, build, master):
        return dict(message='Build done.')

    def render_retry(self, build, master):
        return dict(message='Build started.')

    def render_started(self, build, master):
        return dict(message='Build started.')


class DumbFormatterForReviewPush(Formatter):
    """Formatter to conform the original test case"""

    layout = "{{ message }}"

    def render_success(self, build, master):
        return dict(message='success')

    def render_warnings(self, build, master):
        return dict(message='warnings')

    def render_skipped(self, build, master):
        return dict(message='skipped')

    def render_exception(self, build, master):
        return dict(message='exception')

    def render_cancelled(self, build, master):
        return dict(message='cancelled')

    def render_failure(self, build, master):
        return dict(message='failure')

    def render_retry(self, build, master):
        return dict(message='retry')

    def render_started(self, build, master):
        return dict(message='started')


_headers = {
    # XXX: authorization is overwritten by the github reporters, but the order
    # of the keys in the headers dictionary matters for the test suite

    'Authorization': 'token <token>',
    'User-Agent': 'Buildbot',
}


class GithubReporterTestMixin:

    BASEURL = 'https://api.github.com'
    HEADERS = {
        # XXX: the order of the keys matters for buildbot's test suite
        'User-Agent': 'Ursabot',
        'Authorization': 'token XXYYZZ'
    }
    AUTH = None

    @ensure_deferred
    async def setUp(self):
        self.setUpTestReactor()
        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)
        await self.master.startService()
        self._http = await httpclientservice.HTTPClientService.getFakeService(
            self.master,
            self,
            self.BASEURL,
            auth=self.AUTH,
            headers=self.HEADERS,
            debug=None,
            verify=None
        )
        service = self.setService()
        service.sessionFactory = Mock(return_value=Mock())
        await service.setServiceParent(self.master)


class TestGitHubStatusPush(GithubReporterTestMixin,
                           github.TestGitHubStatusPush):

    def setService(self):
        # test or own implementation
        self.sp = GitHubStatusPush(
            token='XXYYZZ',
            formatter=DumbFormatterForStatusPush()
        )
        return self.sp


class TestGitHubStatusPushURL(GithubReporterTestMixin,
                              github.TestGitHubStatusPushURL):

    def setService(self):
        # test or own implementation
        self.sp = GitHubStatusPush(
            token='XXYYZZ',
            formatter=DumbFormatterForStatusPush()
        )
        return self.sp


class TestGitHubCommentPush(GithubReporterTestMixin,
                            github.TestGitHubCommentPush):

    def setService(self):
        # test or own implementation
        self.sp = GitHubCommentPush(
            token='XXYYZZ',
            formatter=DumbFormatterForReviewPush()
        )
        return self.sp

    @ensure_deferred
    async def test_basic(self):
        build = await self.setupBuildResults(SUCCESS)

        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'started'}
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'success'}
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'failure'}
        )

        build['complete'] = False
        self.sp.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        self.sp.buildFinished(('build', 20, 'finished'), build)


class TestGitHubReviewPush(TestGitHubStatusPush):

    def setService(self):
        self.sp = GitHubReviewPush(
            token='XXYYZZ',
            formatter=DumbFormatterForReviewPush()
        )
        return self.sp

    @ensure_deferred
    async def test_basic(self):
        build = await self.setupBuildResults(SUCCESS)

        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'PENDING',
                'commit_id': 'd34db33fd43db33f',
                'body': 'started'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'APPROVE',
                'commit_id': 'd34db33fd43db33f',
                'body': 'success'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'REQUEST_CHANGES',
                'commit_id': 'd34db33fd43db33f',
                'body': 'failure'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'REQUEST_CHANGES',
                'commit_id': 'd34db33fd43db33f',
                'body': 'exception'
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
