import json
import mock
from collections import namedtuple
from contextlib import contextmanager

from twisted.internet import reactor
from twisted.trial import unittest
from treq.testing import StubTreq, HasHeaders
from treq.testing import RequestSequence, StringStubbingResource
from buildbot.util import httpclientservice
from buildbot.util import service

from ursabot.utils import GithubClientService, ensure_deferred


Request = namedtuple('Request', ['method', 'url', 'params', 'headers', 'data'])
Response = namedtuple('Response', ['code', 'headers', 'body'])


def as_json(data):
    return json.dumps(data).encode('utf-8')


class GithubClientServiceTest(unittest.TestCase):

    @ensure_deferred
    async def setUp(self):
        if httpclientservice.treq is None:
            raise unittest.SkipTest('this test requires treq')

        self.parent = service.MasterService()
        self.parent.reactor = reactor

        self.headers = {}
        self.http = await GithubClientService.getService(
            self.parent,
            'https://api.github.com',
            tokens=['A', 'B', 'C'],
            headers=self.headers
        )
        await self.parent.startService()

    @contextmanager
    def responses(self, responses):
        failures = []
        responses = RequestSequence(responses, failures.append)
        stub = StubTreq(StringStubbingResource(responses))
        self.patch(httpclientservice, 'treq', stub)

        try:
            with responses.consume(self.fail):
                yield
        finally:
            assert failures == []

    @ensure_deferred
    async def test_fetching_rate_limit(self):
        responses = [
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/rate_limit',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token A']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '5000'},
                    body=as_json({'rate': {'remaining': 5000}})
                )
            ),
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/rate_limit',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token B']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '4000'},
                    body=as_json({'rate': {'remaining': 4000}})
                )
            )
        ]
        with self.responses(responses):
            assert await self.http.rate_limit('A') == 5000
            assert await self.http.rate_limit('B') == 4000

    @ensure_deferred
    async def test_basic(self):
        responses = [
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/repos/ursa-labs/ursabot',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token A']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '5000'},
                    body=as_json({})
                )
            )
        ]
        with self.responses(responses):
            await self.http.get('/repos/ursa-labs/ursabot')

    @ensure_deferred
    async def test_rotation_because_of_reaching_limit(self):
        self.http.rotate_at = 1000  # this id the default
        responses = [
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/repos/ursa-labs/ursabot',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token A']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': f'{i}'},
                    body=as_json({})
                )
            )
            for i in (1002, 1001, 1000)
        ] + [
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/rate_limit',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token B']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '5000'},
                    body=as_json({'rate': {'remaining': 5000}})
                )
            ),
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/repos/ursa-labs/ursabot',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token B']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '4999'},
                    body=as_json({})
                )
            )
        ]

        with self.responses(responses):
            for _ in range(4):
                await self.http.get('/repos/ursa-labs/ursabot')

    @ensure_deferred
    async def test_rotation_becasue_of_forbidden_access(self):
        self.http.rotate_at = 1000  # this id the default
        responses = [
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/repos/ursa-labs/ursabot',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token A']}),
                    data=mock.ANY
                ),
                Response(
                    code=403,
                    headers={'X-RateLimit-Remaining': '0'},
                    body=as_json({})
                )
            ),
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/rate_limit',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token B']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '900'},
                    body=as_json({'rate': {'remaining': 900}})
                )
            ),
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/rate_limit',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token C']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '5000'},
                    body=as_json({'rate': {'remaining': 5000}})
                )
            ),
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/repos/ursa-labs/ursabot',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token C']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '4999'},
                    body=as_json({})
                )
            ),
            (
                Request(
                    method=b'get',
                    url='https://api.github.com/repos/ursa-labs/ursabot',
                    params=mock.ANY,
                    headers=HasHeaders({'Authorization': ['token C']}),
                    data=mock.ANY
                ),
                Response(
                    code=200,
                    headers={'X-RateLimit-Remaining': '4998'},
                    body=as_json({})
                )
            )

        ]

        with self.responses(responses):
            await self.http.get('/repos/ursa-labs/ursabot')
            await self.http.get('/repos/ursa-labs/ursabot')
