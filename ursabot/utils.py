import os
import pathlib
import toml
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
            items = filter(fn, items)
        return self.__class__(items)

    def groupby(self, *args):
        return toolz.groupby(operator.attrgetter(*args), self)


class Config(dict):
    __getattr__ = dict.__getitem__

    @classmethod
    def _default_paths(cls):
        env = os.environ.get('URSABOT_ENV', 'default')
        files = ['default.toml', f'{env}.toml', '.secrets.toml']
        paths = list(map(pathlib.Path, files))
        return [p for p in paths if p.exists()]

    @classmethod
    def load(cls, *paths, deserializer=toml.loads):
        paths = paths or cls._default_paths()
        configs = [deserializer(path.read_text())
                   for path in map(pathlib.Path, paths)]
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
