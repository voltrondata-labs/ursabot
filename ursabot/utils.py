import re
import json
import toml
import pathlib
import itertools
import functools
import operator

import toolz
from ruamel.yaml import YAML
from twisted.internet import defer
from buildbot.util.logger import Logger
from buildbot.util.httpclientservice import HTTPClientService


log = Logger()


def ensure_deferred(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        return defer.ensureDeferred(result)

    return wrapper


def slugify(s):
    """Slugify CamelCase name"""
    s = re.sub(r'[\W\-]+', '-', s)
    s = re.sub(r'([A-Z])', lambda m: '-' + m.group(1).lower(), s)
    s = s.strip('-')
    return s


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
    return Filter(lambda s: s.startswith(prefix))


def any_of(*args):
    return Filter(lambda s: s in args)


class Collection(list):

    def filter(self, **kwargs):
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

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return self.__class__(super().__add__(other))
        else:
            return NotImplemented


class ConfigError(Exception):
    pass


class Config(dict):
    __getattr__ = dict.__getitem__

    @classmethod
    def from_path(cls, path):
        path = pathlib.Path(path)

        if path.suffix == '.json':
            loads = json.loads
        elif path.suffix == '.toml':
            loads = toml.loads
        elif path.suffix in ['.yml', '.yaml']:
            loads = YAML().load
        else:
            raise ValueError(f'Unsupported extension: `{path.suffix}`')

        return cls(loads(path.read_text()))

    @classmethod
    def load(cls, *paths, optionals=tuple()):
        configs = [cls.from_path(path) for path in paths]

        for path in optionals:
            try:
                configs.append(cls.from_path(path))
            except FileNotFoundError:
                continue

        return cls.merge(configs)

    @classmethod
    def merge(cls, args):
        if any(isinstance(a, dict) for a in args):
            return toolz.merge_with(cls.merge, *args, factory=cls)
        elif any(isinstance(a, list) for a in args):
            # TODO(kszucs): introduce a strategy argument to concatenate lists
            #               instead of replacing
            # don't merge lists but needs to propagate factory
            return [cls.merge([a]) for a in toolz.last(args)]
        else:
            return toolz.last(args)


class GithubClientService(HTTPClientService):

    PREFER_TREQ = True

    def __init__(self, *args, tokens, rotate_at=1000, max_retries=5, **kwargs):
        assert rotate_at < 5000
        self._tokens = itertools.cycle(tokens)
        self._rotate_at = rotate_at
        self._max_retries = max_retries
        super().__init__(*args, **kwargs)

    def startService(self):
        self._set_token(next(self._tokens))
        return super().startService()

    def _set_token(self, token):
        if self._headers is None:
            self._headers = {}
        self._headers['Authorization']: f'token {token}'

    async def _rotate_tokens(self):
        # try each token, query its rate limit
        # if none of them works log and sleep
        for _, token in zip(len(self._tokens), self._tokens):
            remaining = await self.remaining_rate_limit(token)
            if remaining > self._rotate_at:
                return self._set_token(token)

    async def _do_request(self, method, endpoint, **kwargs):
        for attempt in range(self._max_retries):
            response = await self._doRequest(method, endpoint, **kwargs)
            remaining = response.headers.get('X-RateLimit-Remaining')

            if response.code == 403:
                # signals exceeded rate limit or forbidden access, force rotate
                log.info(f'Failed to fetch endpoint {endpoint} because of '
                         'exceeded rate limit and/or forbidden access. '
                         'Retrying with the next token.')
                await self._rotate_tokens()
                continue

            if remaining is not None and remaining <= self._rotate_at:
                log.info('Remaining rate limit has reached the rotation '
                         'limit, switching to the next token.')
                await self._rotate_tokens()

            return response

    def get(self, endpoint, **kwargs):
        return self._do_request('get', endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        return self._do_request('put', endpoint, **kwargs)

    def delete(self, endpoint, **kwargs):
        return self._do_request('delete', endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self._do_request('post', endpoint, **kwargs)

    async def remaining_rate_limit(self, token=None):
        headers = {}
        if token is not None:
            headers['Authorization']: f'token {token}'

        response = await self.get('/rate_limit', headers=headers)
        data = await response.json()

        return data['rate']['remaining']
