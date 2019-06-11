import json
from pathlib import Path
from twisted.trial import unittest

from buildbot.plugins import util
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.www.change_hook import ChangeHookResource
from buildbot.test.unit.test_www_hooks_github import _prepare_request
from buildbot.test.fake.httpclientservice import \
    HTTPClientService as FakeHTTPClientService

from ursabot.utils import ensure_deferred
from ursabot.hooks import UrsabotHook
from ursabot.commands import CommandError, ursabot as ursabot_command


def _prepare_github_change_hook(testcase, **params):
    return ChangeHookResource(
        dialects={
            'github': params
        },
        master=fakeMasterForHooks(testcase)
    )


class ChangeHookTestCase(unittest.TestCase, TestReactorMixin):

    klass = None

    @ensure_deferred
    async def setUp(self):
        self.setUpTestReactor()

        assert self.klass is not None
        self.hook = _prepare_github_change_hook(self, **{
            'class': self.klass,
            'token': util.Interpolate('test-token')
        })
        self.master = self.hook.master
        self.http = await FakeHTTPClientService.getFakeService(
            self.master,
            self,
            'https://api.github.com',
            headers={
                'User-Agent': 'ursabot',
                'Authorization': 'token test-token'
            },
            debug=False,
            verify=False
        )

        await self.master.startService()

    @ensure_deferred
    async def tearDown(self):
        await self.master.stopService()

    async def trigger(self, event, payload, headers=None, _secret=None):
        payload = json.dumps(payload).encode()
        request = _prepare_request(event, payload, _secret=_secret,
                                   headers=headers)
        await request.test_render(self.hook)
        return request

    def load_fixture(self, name):
        path = Path(__file__).parent / 'fixtures' / f'{name}.json'
        with path.open('r') as fp:
            return json.load(fp)


class TestUrsabotHook(ChangeHookTestCase):

    klass = UrsabotHook

    @ensure_deferred
    async def test_ping(self):
        await self.trigger('ping', {})
        assert len(self.hook.master.data.updates.changesAdded) == 0

    @ensure_deferred
    async def test_issue_comment_not_mentioning_ursabot(self):
        payload = self.load_fixture('issue-comment-not-mentioning-ursabot')
        await self.trigger('issue_comment', payload=payload)
        assert len(self.hook.master.data.updates.changesAdded) == 0

    @ensure_deferred
    async def test_issue_comment_by_ursabot(self):
        # don't respond to itself, it prevents recursive comment storms!
        payload = self.load_fixture('issue-comment-by-ursabot')
        await self.trigger('issue_comment', payload=payload)
        assert len(self.hook.master.data.updates.changesAdded) == 0

    @ensure_deferred
    async def test_issue_comment_by_non_authorized_user(self):
        payload = self.load_fixture('issue-comment-by-non-authorized-user')
        await self.trigger('issue_comment', payload=payload)
        assert len(self.hook.master.data.updates.changesAdded) == 0

    @ensure_deferred
    async def test_issue_comment_with_empty_command_reponds_with_usage(self):
        # responds to the comment with the usage
        try:
            ursabot_command('')
        except CommandError as e:
            usage = e.message

        request_json = {'body': usage}
        response_json = ''
        self.http.expect('post', '/repos/ursa-labs/ursabot/issues/26/comments',
                         json=request_json, content_json=response_json)

        payload = self.load_fixture('issue-comment-with-empty-command')
        await self.trigger('issue_comment', payload=payload)
        assert len(self.hook.master.data.updates.changesAdded) == 0

    @ensure_deferred
    async def test_issue_comment_without_pull_request(self):
        # responds to the comment
        request_json = {
            'body': 'Ursabot only listens to pull request comments!'
        }
        response_json = ''
        self.http.expect('post', '/repos/ursa-labs/ursabot/issues/19/comments',
                         json=request_json, content_json=response_json)

        payload = self.load_fixture('issue-comment-without-pull-request')
        await self.trigger('issue_comment', payload=payload)
        assert len(self.hook.master.data.updates.changesAdded) == 0

    @ensure_deferred
    async def check_issue_comment_with_command(self, command, props=None):
        # handle_issue_comment queries the pull request
        request_json = self.load_fixture('pull-request-26')
        self.http.expect('get', '/repos/ursa-labs/ursabot/pulls/26',
                         content_json=request_json)
        # trigger handle_pull_request which fetches the commit
        request_json = self.load_fixture('pull-request-26-commit')
        commit = '2705da2b616b98fa6010a25813c5a7a27456f71d'
        self.http.expect('get', f'/repos/ursa-labs/ursabot/commits/{commit}',
                         content_json=request_json)

        # then responds to the comment
        request_json = {'body': "I've successfully started builds for this PR"}
        response_json = ''
        self.http.expect('post', '/repos/ursa-labs/ursabot/issues/26/comments',
                         json=request_json, content_json=response_json)

        payload = self.load_fixture('issue-comment-build-command')
        payload['comment']['body'] = f'@ursabot {command}'
        await self.trigger('issue_comment', payload=payload)

        expected_title = 'Unittests for GithubHook'

        assert len(self.hook.master.data.updates.changesAdded) == 1
        for change in self.hook.master.data.updates.changesAdded:
            assert change['properties']['event'] == 'issue_comment'
            assert change['properties']['github.title'] == expected_title
            for k, v in props.items():
                assert change['properties'][k] == v

    @ensure_deferred
    async def test_issue_comment_build_command(self):
        await self.check_issue_comment_with_command(
            'build',
            {'command': 'build'}
        )

    @ensure_deferred
    async def test_issue_comment_benchmark_command(self):
        await self.check_issue_comment_with_command(
            'benchmark',
            {'command': 'benchmark'}
        )

    @ensure_deferred
    async def test_issue_comment_crosssbow_test_command(self):
        await self.check_issue_comment_with_command(
            'crossbow test docker',
            {
                'command': 'crossbow',
                'crossbow_args': ['-c', 'tests.yml', '-g', 'docker']
            }
        )

    @ensure_deferred
    async def test_issue_comment_crosssbow_package_command(self):
        await self.check_issue_comment_with_command(
            'crossbow package wheel conda',
            {
                'command': 'crossbow',
                'crossbow_args': ['-c', 'tasks.yml', '-g', 'wheel', '-g',
                                  'conda']
            }
        )
