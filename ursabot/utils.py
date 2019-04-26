import os
import pathlib
import toml
import toolz
import functools
from twisted.internet import defer


def ensure_deferred(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        return defer.ensureDeferred(result)

    return wrapper


def attrfilter(obj, **kwargs):
    items = obj
    for by, value in kwargs.items():
        if callable(value):
            fn = lambda item: value(getattr(item, by))  # noqa:E731
        else:
            fn = lambda item: getattr(item, by) == value  # noqa:E731
        items = filter(fn, items)
    return type(obj)(items)


class Collection(list):

    def filter(self, **kwargs):
        return attrfilter(self, **kwargs)


def deepmerge(args, factory=dict):
    fn = functools.partial(deepmerge, factory=factory)
    if any(isinstance(a, dict) for a in args):
        return toolz.merge_with(fn, *args, factory=factory)
    elif any(isinstance(a, list) for a in args):
        # don't merge lists but needs to propagate factory
        return [fn([a]) for a in toolz.last(args)]
    else:
        return toolz.last(args)


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
        return deepmerge(configs, factory=cls)
