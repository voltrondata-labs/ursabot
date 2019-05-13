# flake8: noqa  todo removeme
from buildbot.process.results import FAILURE, SUCCESS, EXCEPTION
from buildbot.test.unit import test_reporter_github as original

from ursabot.reporters import (GitHubStatusPush, GitHubReviewPush,
                               GitHubCommentPush)
from ursabot.utils import ensure_deferred


class TestGitHubStatusPush(original.TestGitHubStatusPush):

    def setService(self):
        # test or own implementation
        self.sp = GitHubStatusPush(token='XXYYZZ')
        return self.sp


class TestGitHubStatusPushURL(original.TestGitHubStatusPushURL):
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


class TestGitHubCommentPush(original.TestGitHubCommentPush):

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
