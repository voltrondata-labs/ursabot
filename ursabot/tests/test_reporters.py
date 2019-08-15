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
from twisted.trial import unittest
from buildbot.config import ConfigErrors
from buildbot.process.properties import Property, Interpolate, renderer
from buildbot.process.results import SUCCESS, FAILURE, EXCEPTION, Results
from buildbot.test.fake import fakemaster
from buildbot.test.fake.httpclientservice import HTTPClientService
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin

from ursabot.reporters import (HttpStatusPush, ZulipStatusPush,
                               GitHubStatusPush, GitHubReviewPush,
                               GitHubCommentPush)
from ursabot.formatters import Formatter
from ursabot.builders import Builder
from ursabot.utils import ensure_deferred
from ursabot.tests.mocks import GithubClientService


class HttpReporterTestCase(TestReactorMixin, unittest.TestCase,
                           ReporterTestMixin):
    # License note:
    #    Copied from the original buildbot implementation with
    #    minor changes and additions.

    # project must be in the form <owner>/<project>
    TEST_PROJECT = 'buildbot/buildbot'
    # XXX: the order of the keys matters for buildbot's test suite
    HEADERS = {'User-Agent': 'Ursabot'}
    AUTH = None

    @ensure_deferred
    async def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)
        self._http = await self.setupClient()
        await self.master.startService()

    def tearDown(self):
        if self.master.running:
            return self.master.stopService()

    def setupClient(self):
        return HTTPClientService.getFakeService(
            self.master,
            self,
            self.BASEURL,
            auth=self.AUTH,
            headers=self.HEADERS,
            debug=False,
            verify=None
        )

    def setupReporter(self):
        raise NotImplementedError()

    @ensure_deferred
    async def setupBuildResults(self, build_results, complete=False,
                                insertSS=True):
        self.insertTestData([build_results], build_results, insertSS=insertSS)
        build = await self.master.data.get(('builds', 20))
        builder = await self.master.data.get(('builders', build['builderid']))
        build['builder'] = builder
        build['complete'] = complete
        return build


class TestHttpStatusPush(HttpReporterTestCase):

    BASEURL = 'http://example.com'

    async def setupReporter(self, **kwargs):
        reporter = HttpStatusPush(name='test', baseURL=self.BASEURL, **kwargs)
        await reporter.setServiceParent(self.master)
        return reporter

    async def check_report_on(self, whitelist, blacklist, expected):
        reporter = await self.setupReporter(report_on=whitelist,
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
    async def test_builders_argument(self):
        with pytest.raises(ConfigErrors):
            HttpStatusPush(name='test', baseURL=self.BASEURL, builders=[1, 2])

        HttpStatusPush(name='test', baseURL=self.BASEURL, builders=['a', 'b'])
        HttpStatusPush(name='test', baseURL=self.BASEURL, builders=[
            Builder(name='a', workers=['a'])
        ])

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
        reporter = await self.setupReporter(builders=None)
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert reporter.filterBuilds(build)

    @ensure_deferred
    async def test_filter_builds_with_empty_list_of_builders(self):
        reporter = await self.setupReporter(builders=[])
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert not reporter.filterBuilds(build)

    @ensure_deferred
    async def test_filter_builds_should_report_on_builder(self):
        reporter = await self.setupReporter(builders=['Builder0'])
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert reporter.filterBuilds(build)

    @ensure_deferred
    async def test_filter_builds_should_not_report_on_builder(self):
        reporter = await self.setupReporter(builders=['Builder1'])
        build = await self.setupBuildResults(SUCCESS, complete=True)
        assert not reporter.filterBuilds(build)


class DumbFormatter(Formatter):

    layout = '{message}'

    async def render_success(self, build, master):
        return dict(message='success')

    async def render_warnings(self, build, master):
        return dict(message='warnings')

    async def render_skipped(self, build, master):
        return dict(message='skipped')

    async def render_exception(self, build, master):
        return dict(message='exception')

    async def render_cancelled(self, build, master):
        return dict(message='cancelled')

    async def render_failure(self, build, master):
        return dict(message='failure')

    async def render_retry(self, build, master):
        return dict(message='retry')

    async def render_started(self, build, master):
        return dict(message='started')


class GithubReporterTestCase(HttpReporterTestCase):

    BASEURL = 'https://api.github.com'
    HEADERS = {'User-Agent': 'Ursabot'}
    TOKENS = ['xyz']

    def setupClient(self):
        return GithubClientService.getFakeService(
            self.master,
            self,
            self.BASEURL,
            tokens=self.TOKENS,
            auth=self.AUTH,
            headers=self.HEADERS,
            debug=False,
            verify=None
        )

    async def setupReporter(self):
        reporter = self.Reporter(tokens=self.TOKENS, formatter=DumbFormatter())
        await reporter.setServiceParent(self.master)
        return reporter


class TestGitHubStatusPush(GithubReporterTestCase):
    # License note:
    #    Copied from the original buildbot implementation with
    #    minor changes and additions.

    Reporter = GitHubStatusPush

    @ensure_deferred
    async def test_basic(self):
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/statuses/d34db33fd43db33f',
            json={
                'state': 'pending',
                'target_url': 'http://localhost:8080/#builders/79/builds/0',
                'description': 'started',
                'context': 'ursabot/Builder0'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/statuses/d34db33fd43db33f',
            json={
                'state': 'success',
                'target_url': 'http://localhost:8080/#builders/79/builds/0',
                'description': 'success',
                'context': 'ursabot/Builder0'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/statuses/d34db33fd43db33f',
            json={
                'state': 'failure',
                'target_url': 'http://localhost:8080/#builders/79/builds/0',
                'description': 'failure',
                'context': 'ursabot/Builder0'
            }
        )

        reporter = await self.setupReporter()
        build = await self.setupBuildResults(SUCCESS, complete=False)

        reporter.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        reporter.buildFinished(('build', 20, 'finished'), build)

    @ensure_deferred
    async def test_empty(self):
        reporter = await self.setupReporter()
        build = await self.setupBuildResults(SUCCESS, complete=False,
                                             insertSS=False)

        reporter.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        reporter.buildFinished(('build', 20, 'finished'), build)


class TestGitHubCommentPush(GithubReporterTestCase):
    # License note:
    #    Copied from the original buildbot implementation with
    #    minor changes and additions.

    Reporter = GitHubCommentPush

    @ensure_deferred
    async def test_basic(self):
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

        reporter = await self.setupReporter()
        build = await self.setupBuildResults(SUCCESS, complete=False)

        reporter.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        reporter.buildFinished(('build', 20, 'finished'), build)

    @ensure_deferred
    async def test_empty(self):
        reporter = await self.setupReporter()
        build = await self.setupBuildResults(SUCCESS, complete=False,
                                             insertSS=False)

        reporter.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        reporter.buildFinished(('build', 20, 'finished'), build)


class TestGitHubReviewPush(GithubReporterTestCase):

    Reporter = GitHubReviewPush

    @ensure_deferred
    async def test_basic(self):
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

        reporter = await self.setupReporter()
        build = await self.setupBuildResults(SUCCESS, complete=False)

        reporter.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = EXCEPTION
        reporter.buildFinished(('build', 20, 'finished'), build)


class TestZulipStatusPush(HttpReporterTestCase):

    TEST_PROJECT = 'blue/berry'
    BASEURL = 'https://testorg.zulipchat.com/api/v1'
    HEADERS = {'User-Agent': 'Ursabot'}
    AUTH = ('ursabot', 'secret')

    async def setupReporter(self, **kwargs):
        reporter = ZulipStatusPush(organization='testorg', bot='ursabot',
                                   apikey='secret', stream='blueberry',
                                   formatter=DumbFormatter(), **kwargs)
        await reporter.setServiceParent(self.master)
        return reporter

    @ensure_deferred
    async def test_topic_is_renderable(self):
        @renderer
        def branch(props):
            return props.getProperty('branch')

        await self.setupReporter(name='a', topic='test')
        await self.setupReporter(name='d', topic=branch)
        await self.setupReporter(name='b', topic=Property('branch'))
        await self.setupReporter(name='c', topic=Interpolate('%(prop:event)s'))

    @ensure_deferred
    async def test_basic(self):
        self._http.expect(
            'post',
            '/messages',
            data={
                'type': 'stream',
                'to': 'blueberry',
                'subject': 'Builder0',
                'content': 'started'
            }
        )
        self._http.expect(
            'post',
            '/messages',
            data={
                'type': 'stream',
                'to': 'blueberry',
                'subject': 'Builder0',
                'content': 'success'
            }
        )
        self._http.expect(
            'post',
            '/messages',
            data={
                'type': 'stream',
                'to': 'blueberry',
                'subject': 'Builder0',
                'content': 'exception'
            }
        )
        self._http.expect(
            'post',
            '/messages',
            data={
                'type': 'stream',
                'to': 'blueberry',
                'subject': 'Builder0',
                'content': 'failure'
            }
        )

        reporter = await self.setupReporter(topic=Property('buildername'))
        build = await self.setupBuildResults(SUCCESS, complete=False)

        reporter.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = EXCEPTION
        reporter.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        reporter.buildFinished(('build', 20, 'finished'), build)

    @ensure_deferred
    async def test_custom_topic(self):
        self._http.expect(
            'post',
            '/messages',
            data={
                'type': 'stream',
                'to': 'blueberry',
                'subject': 'refs/pull/34/merge',
                'content': 'started'
            }
        )
        self._http.expect(
            'post',
            '/messages',
            data={
                'type': 'stream',
                'to': 'blueberry',
                'subject': 'refs/pull/34/merge',
                'content': 'success'
            }
        )

        reporter = await self.setupReporter(topic=Property('branch'))
        build = await self.setupBuildResults(SUCCESS, complete=False)

        reporter.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        reporter.buildFinished(('build', 20, 'finished'), build)
