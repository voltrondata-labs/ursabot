import re
import json
import toml
import pathlib
import toolz
import functools
import operator
from twisted.internet import defer


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
    def load(cls, *files):
        paths = list(map(pathlib.Path, files))

        configs = []
        for path in paths:
            if path.suffix == '.json':
                loads = json.loads
            elif path.suffix == '.toml':
                loads = toml.loads
            else:
                raise ValueError(f'Unsupported extension: `{path.suffix}`')

            # loading .secrets.ext files is optional
            if not path.exists() and 'secret' in path.name:
                continue
            configs.append(loads(path.read_text()))

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
