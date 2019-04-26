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
            configs.append(loads(path.read_text()))

        return cls.merge(configs)

    @classmethod
    def merge(cls, args):
        if any(isinstance(a, dict) for a in args):
            return toolz.merge_with(cls.merge, *args, factory=cls)
        elif any(isinstance(a, list) for a in args):
            # don't merge lists but needs to propagate factory
            return [cls.merge([a]) for a in toolz.last(args)]
        else:
            return toolz.last(args)
