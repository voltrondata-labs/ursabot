import json
from twisted.trial import unittest

from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.fake.httpclientservice import \
    HTTPClientService as FakeHTTPClientService
from buildbot.test.unit.test_www_hooks_github import (
    _prepare_request, _prepare_github_change_hook)

from ursabot.utils import ensure_deferred
from ursabot.hooks import GithubHook

# use pip install --no-binary buildbot buildbot to install from source, because
# buildbot doesn't bundle tests in wheels

# requires pip install pytest-twisted


class ChangeHookTestCase(unittest.TestCase, TestReactorMixin):

    klass = None

    @ensure_deferred
    async def setUp(self):
        self.setUpTestReactor()

        assert self.klass is not None
        self.hook = _prepare_github_change_hook(self, **{'class': self.klass})
        self.master = self.hook.master
        self.http = await FakeHTTPClientService.getFakeService(
            self.master, self, 'https://api.github.com',
            headers={'User-Agent': 'Buildbot'}, debug=False, verify=False)

        await self.master.startService()

    @ensure_deferred
    async def tearDown(self):
        await self.master.stopService()

    async def request(self, event, payload, _secret=None, headers=None):
        payload = json.dumps(payload).encode()
        request = _prepare_request(event, payload, _secret=_secret,
                                   headers=headers)
        await request.test_render(self.hook)
        return request


class TestGithubHook(ChangeHookTestCase):

    klass = GithubHook

    @ensure_deferred
    async def test_ping(self):
        await self.request('ping', {})
        assert len(self.hook.master.data.updates.changesAdded) == 0

    @ensure_deferred
    async def test_issue_comment(self):
        payload = {}
        await self.request('issue_comment', payload)
