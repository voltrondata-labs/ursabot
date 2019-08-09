# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import pathlib
import fnmatch
import itertools
import functools
import operator

import toolz
from twisted.internet import defer
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger

__all__ = [
    'ensure_deferred',
    'read_dependency_list',
    'Filter',
    'startswith',
    'any_of',
    'has',
    'Collection',
    'HTTPClientService',
    'GithubClientService',
]

log = Logger()


def ensure_deferred(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        return defer.ensureDeferred(result)

    return wrapper


def read_dependency_list(path):
    """Parse plaintext files with comments as list of dependencies"""
    path = pathlib.Path(path)
    lines = (l.strip() for l in path.read_text().splitlines())
    return [l for l in lines if not l.startswith('#')]


class Filter:

    __slot__ = ('fn',)

    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    @classmethod
    def _binop(cls, fn, other):
        if isinstance(other, cls):
            return cls(fn)
        else:
            return NotImplemented

    def __or__(self, other):
        def _or(*args, **kwargs):
            return self(*args, **kwargs) or other(*args, **kwargs)
        return self._binop(_or, other)

    def __and__(self, other):
        def _and(*args, **kwargs):
            return self(*args, **kwargs) and other(*args, **kwargs)
        return self._binop(_and, other)


def startswith(prefix):
    return Filter(lambda value: value.startswith(prefix))


def any_of(*values):
    return Filter(lambda value: value in values)


def has(*needles):
    return Filter(lambda haystack: set(needles).issubset(set(haystack)))


def matching(glob_pattern):
    return Filter(lambda value: fnmatch.fnmatch(value, glob_pattern))


def any_matching(glob_pattern):
    return Filter(lambda values: bool(fnmatch.filter(values, glob_pattern)))


class Collection(list):

    def get(self, **kwargs):
        """Retrieves a single entry from the collection."""
        results = self.filter(**kwargs)
        if len(results) == 0:
            raise KeyError('No entry can be found by the filter conditions')
        elif len(results) > 1:
            raise KeyError('Multiple entries can be found by the conditions')
        else:
            return results[0]

    def filter(self, **kwargs):
        """Filters the values based on the passed conditions.

        The filters can be passed as property=(value or filter function) form.
        """
        items = self
        for by, value in kwargs.items():
            if callable(value):
                fn = lambda item: value(getattr(item, by))  # noqa:E731
            else:
                fn = lambda item: getattr(item, by) == value  # noqa:E731
            # XXX: without consuming the iterator only the first filter works
            items = tuple(filter(fn, items))
        return self.__class__(items)

    def groupby(self, *args):
        return toolz.groupby(operator.attrgetter(*args), self)

    def unique(self):
        return self.__class__(toolz.unique(self))

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return self.__class__(super().__add__(other))
        else:
            return NotImplemented


class HTTPClientService(httpclientservice.HTTPClientService):

    PREFER_TREQ = True

    def _prepareRequest(self, ep, kwargs):
        # XXX: originally the default headers and the headers received as an
        # arguments were merged in the wrong order
        default_headers = self._headers or {}
        headers = kwargs.pop('headers', None) or {}

        url, kwargs = super()._prepareRequest(ep, kwargs)
        kwargs['headers'] = {**default_headers, **headers}

        return url, kwargs


class GithubClientService(HTTPClientService):

    def __init__(self, *args, tokens, rotate_at=1000, max_retries=5,
                 headers=None, **kwargs):
        assert rotate_at < 5000
        tokens = list(tokens)
        self._tokens = itertools.cycle(tokens)
        self._n_tokens = len(tokens)
        self._rotate_at = rotate_at
        self._max_retries = max_retries
        headers = headers or {}
        headers.setdefault('User-Agent', 'Buildbot')
        super().__init__(*args, headers=headers, **kwargs)

    def startService(self):
        self._set_token(next(self._tokens))
        return super().startService()

    def _set_token(self, token):
        if self._headers is None:
            self._headers = {}
        self._headers['Authorization'] = f'token {token}'

    @ensure_deferred
    async def rate_limit(self, token=None):
        headers = {}
        if token is not None:
            headers['Authorization'] = f'token {token}'

        response = await self._doRequest('get', '/rate_limit', headers=headers)
        data = await response.json()

        return data['rate']['remaining']

    @ensure_deferred
    async def rotate_tokens(self):
        # try each token, query its rate limit
        # if none of them works log and sleep
        for token in toolz.take(self._n_tokens, self._tokens):
            remaining = await self.rate_limit(token)

            if remaining > self._rotate_at:
                return self._set_token(token)

    @ensure_deferred
    async def _do_request(self, method, endpoint, **kwargs):
        for attempt in range(self._max_retries):
            response = await self._doRequest(method, endpoint, **kwargs)
            headers, code = response.headers, response.code

            if code // 100 == 4:
                if code == 401:
                    # Unauthorized: bad credentials
                    reason = 'bad credentials (401)'
                elif code == 403:
                    # Forbidden: exceeded rate limit or forbidden access
                    reason = 'exceeded rate limit or forbidden access (403)'
                elif code == 404:
                    # Requests that require authentication will return 404 Not
                    # Found, instead of 403 Forbidden, in some places. This is
                    # to prevent the accidental leakage of private repositories
                    # to unauthorized users.
                    reason = 'resource not found (404)'
                else:
                    reason = f'status code {code}'

                log.info(f'Failed to fetch endpoint {endpoint} because of '
                         f' {reason}. Retrying with the next token.')
                await self.rotate_tokens()
            else:
                if headers.hasHeader('X-RateLimit-Remaining'):
                    values = headers.getRawHeaders('X-RateLimit-Remaining')
                    remaining = int(toolz.first(values))
                    if remaining <= self._rotate_at:
                        log.info('Remaining rate limit has reached the '
                                 'rotation limit, switching to the next '
                                 'token.')
                        await self.rotate_tokens()
                break

        return response

    def get(self, endpoint, **kwargs):
        return self._do_request('get', endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        return self._do_request('put', endpoint, **kwargs)

    def delete(self, endpoint, **kwargs):
        return self._do_request('delete', endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self._do_request('post', endpoint, **kwargs)
