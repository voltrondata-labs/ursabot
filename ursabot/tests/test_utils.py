# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.
#
# This file contains function or sections of code that are marked as being
# derivative works of Buildbot. The above license only applies to code that
# is not marked as such.

import json
import mock
from collections import namedtuple
from contextlib import contextmanager

from twisted.internet import reactor
from twisted.trial import unittest
from buildbot.util import httpclientservice
from buildbot.util import service

from ursabot.utils import (GithubClientService, Collection, LazyObject,
                           ensure_deferred, startswith)


def test_collection():
    Item = namedtuple('Item', ('name', 'id'))
    items = Collection([
        Item(name='tset', id=1),
        Item(name='test', id=2),
        Item(name='else', id=3),
        Item(name='test', id=4),
        Item(name='test', id=4)
    ])
    items2 = Collection([
        Item(name='test1', id=5),
        Item(name='test2', id=6)
    ])

    assert items.filter(id=1) == Collection([
        Item(name='tset', id=1)
    ])
    assert items.filter(name='test', id=2) == Collection([
        Item(name='test', id=2)
    ])
    assert items.filter(name=startswith('t')) == Collection([
        Item(name='tset', id=1),
        Item(name='test', id=2),
        Item(name='test', id=4),
        Item(name='test', id=4)
    ])
    assert items.filter(name=startswith('t')).unique() == Collection([
        Item(name='tset', id=1),
        Item(name='test', id=2),
        Item(name='test', id=4)
    ])
    assert (items + items2) == Collection([
        Item(name='tset', id=1),
        Item(name='test', id=2),
        Item(name='else', id=3),
        Item(name='test', id=4),
        Item(name='test', id=4),
        Item(name='test1', id=5),
        Item(name='test2', id=6)
    ])
    assert items.filter(name=startswith('t')).groupby('name') == {
        'tset': [
            Item(name='tset', id=1)
        ],
        'test': [
            Item(name='test', id=2),
            Item(name='test', id=4),
            Item(name='test', id=4)
        ]
    }


# def test_lazy_collection():
#     Item = namedtuple('Item', ('name', 'id'))
#     items = Collection([
#         Item(name='tset', id=1),
#         Item(name='test', id=2),
#         Item(name='else', id=3),
#         Item(name='test', id=4),
#         Item(name='test', id=4)
#     ])
#
#     lazy = LazyObject(Collection)
#     plan = lazy.filter(name='test').unique()
#     plan2 = lazy.filter(name=startswith('t')).groupby('id')
#     result = plan.execute(items)
#     result2 = plan2.execute(items)
#
#     assert result == Collection([
#         Item(name='test', id=2),
#         Item(name='test', id=4)
#     ])
#     assert result2 == {
#         1: [
#             Item(name='tset', id=1)
#         ],
#         2: [
#             Item(name='test', id=2)
#         ],
#         4: [
#             Item(name='test', id=4),
#             Item(name='test', id=4)
#         ]
#     }


Request = namedtuple('Request', ['method', 'url', 'params', 'headers', 'data'])
Response = namedtuple('Response', ['code', 'headers', 'body'])


def as_json(data):
    return json.dumps(data).encode('utf-8')


class GithubClientServiceTest(unittest.TestCase):

    @ensure_deferred
    async def setUp(self):
        # License note:
        #    Copied from the original buildbot implementation with
        #    minor changes and additions.

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
        # otherwise it bails pytest because of a DeprecationWarning
        from treq.testing import StubTreq
        from treq.testing import RequestSequence, StringStubbingResource

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
        from treq.testing import HasHeaders

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
        from treq.testing import HasHeaders

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
        from treq.testing import HasHeaders

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
        from treq.testing import HasHeaders

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
