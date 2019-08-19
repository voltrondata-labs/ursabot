# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.
#
# This file contains function or sections of code that are marked as being
# derivative works of Buildbot. The above license only applies to code that
# is not marked as such.

import sys
import operator
import traceback
from pathlib import Path
from functools import reduce
from contextlib import contextmanager
from typing import List, Callable, Optional

import toolz
from pydantic import BaseModel
from twisted.python.compat import execfile
from zope.interface import implementer
from buildbot import interfaces
from buildbot.worker.base import AbstractWorker
from buildbot.changes.base import ChangeSource
from buildbot.schedulers.base import BaseScheduler
from buildbot.reporters.http import HttpStatusPushBase
from buildbot.config import ConfigErrors, error, _errors  # noqa
from buildbot.config import MasterConfig as BuildbotMasterConfig
from buildbot.util.logger import Logger
from buildbot.util import ComparableMixin
from buildbot.www.auth import AuthBase
from buildbot.www.authz import Authz
from buildbot.secrets.providers.base import SecretProviderBase

from .docker import ImageCollection
from .hooks import GithubHook
from .builders import Builder

__all__ = [
    'Config',
    'ProjectConfig',
    'MasterConfig',
    'InMemoryLoader',
    'FileLoader',
    'BuildmasterConfigLoader',
    'collect_global_errors'
]

log = Logger()


@contextmanager
def collect_global_errors(and_raise=False):
    global _errors
    _errors = errors = ConfigErrors()

    try:
        yield errors
    except ConfigErrors as e:
        errors.merge(e)
    finally:
        _errors = None
        if errors and and_raise:
            raise errors


class Config(BaseModel):

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def load_from(cls, path, variable, inject_globals=None):
        loader = FileLoader(path, variable=variable,
                            inject_globals=inject_globals)
        config = loader.load()
        assert isinstance(config, cls)
        return config


class ProjectConfig(Config):

    name: str
    repo: str
    images: ImageCollection = []
    commands: List[Callable] = []
    pollers: List[ChangeSource] = []
    workers: List[AbstractWorker] = []
    builders: List[Builder] = []
    schedulers: List[BaseScheduler] = []
    reporters: List[HttpStatusPushBase] = []


class MasterConfig(Config):

    projects: List[ProjectConfig]
    title: str = 'Ursabot'
    url: str = 'http://localhost:8100'
    webui_port: int = 8100
    worker_port: int = 9989
    database_url: str = 'sqlite:///ursabot.sqlite'
    auth: Optional[AuthBase] = None
    authz: Optional[Authz] = None
    change_hook: GithubHook = None
    secret_providers: List[SecretProviderBase] = []

    def project(self, name=None):
        """Select one of the projects defined in the MasterConfig

        Parameters
        ----------
        name: str, default None
            Name of the project. If None is passed and the master has a single
            project configured, then return with that.

        Returns
        -------
        project: ProjectConfig
        """
        if name is None:
            if len(self.projects) == 1:
                return self.projects[0]
            else:
                project_names = ', '.join(p.name for p in self.projects)
                raise ValueError(f'Master config has multiple projects, one '
                                 f'must be selected: {project_names}')
        else:
            return self.projects.filter(name=name)[0]

    def _from_projects(self, key, unique=False):
        values = (getattr(p, key) for p in self.projects)
        values = reduce(operator.add, values)
        if unique:
            values = toolz.unique(values)
        return list(values)

    @property
    def images(self):
        return ImageCollection(self._from_projects('images'))

    @property
    def commands(self):
        return self._from_projects('commands')

    @property
    def workers(self):
        return self._from_projects('workers', unique=True)

    @property
    def builders(self):
        return self._from_projects('builders')

    @property
    def pollers(self):
        return self._from_projects('pollers')

    @property
    def schedulers(self):
        return self._from_projects('schedulers')

    @property
    def reporters(self):
        return self._from_projects('reporters')

    def as_testing(self, source):
        builder_configs = [b.as_config() for b in self.builders]
        buildbot_config_dict = {
            'buildbotNetUsageData': None,
            'workers': self.workers,
            'builders': builder_configs,
            'schedulers': self.schedulers,
            'db': {'db_url': 'sqlite://'},
            'protocols': {'pb': {'port': 'tcp:0:interface=127.0.0.1'}}
        }
        return BuildbotMasterConfig.loadFromDict(buildbot_config_dict,
                                                 filename=source)

    def as_buildbot(self, source):
        """Returns with the buildbot compatible buildmaster configuration"""

        if self.change_hook is None:
            hook_dialect_config = {}
        else:
            hook_dialect_config = self.change_hook._as_hook_dialect_config()

        builder_configs = [b.as_config() for b in self.builders]
        buildbot_config_dict = {
            'buildbotNetUsageData': None,
            'title': self.title,
            'titleURL': self.url,
            'buildbotURL': self.url,
            'workers': self.workers,
            'builders': builder_configs,
            'schedulers': self.schedulers,
            'services': self.reporters,
            'change_source': self.pollers,
            'secretsProviders': self.secret_providers or [],
            'protocols': {'pb': {'port': self.worker_port}},
            'db': {'db_url': self.database_url},
            'www': {
                'port': self.webui_port,
                'change_hook_dialects': hook_dialect_config,
                'plugins': {
                    'waterfall_view': {},
                    'console_view': {},
                    'grid_view': {}
                }
            }
        }

        # buildbot raises errors for None or empty dict values so only set of
        # they are passed
        if self.auth is not None:
            buildbot_config_dict['www']['auth'] = self.auth
        if self.authz is not None:
            buildbot_config_dict['www']['authz'] = self.authz

        return BuildbotMasterConfig.loadFromDict(buildbot_config_dict,
                                                 filename=source)


@implementer(interfaces.IConfigLoader)
class InMemoryLoader:

    def __init__(self, config, source='<memory>'):
        self.config = config
        self.source = source

    def loadConfig(self):
        with collect_global_errors(and_raise=True):
            return self.config.as_buildbot(self.source)


@implementer(interfaces.IConfigLoader)
class FileLoader(ComparableMixin):

    compare_attrs = ['path', 'variable', 'inject_globals']

    def __init__(self, path, variable, inject_globals=None):
        self.path = Path(path)
        self.variable = variable
        self.inject_globals = inject_globals or {}

    def load(self):
        # License note:
        #     It is a reimplementation based on the original
        #     buildbot.config.FileLoader and buildbot.config.loadConfigDict
        #     implementation.
        config = self.path.absolute()
        basedir = config.parent

        if not config.exists():
            raise ConfigErrors([
                f"configuration file '{config}' does not exist"
            ])

        try:
            with config.open('r'):
                pass
        except IOError as e:
            raise ConfigErrors([
                f'unable to open configuration file {config}: {e}'
            ])

        log.info(f'Loading configuration from {config}')

        # execute the config file
        local_dict = {
            # inject global variables, useful for including configurations
            **self.inject_globals,
            # TODO(kszucs): is it required?
            'basedir': basedir.expanduser(),
            '__file__': config
        }

        old_sys_path = sys.path[:]
        sys.path.append(str(basedir))
        try:
            try:
                execfile(config, local_dict)
            except ConfigErrors:
                raise
            except SyntaxError:
                exc = traceback.format_exc()
                error(f'encountered a SyntaxError while parsing config file:\n'
                      f'{exc}', always_raise=True)
            except Exception:
                exc = traceback.format_exc()
                error(f'error while parsing config file: {exc} (traceback in '
                      f'logfile)', always_raise=True)
        finally:
            sys.path[:] = old_sys_path

        if self.variable not in local_dict:
            error(f'Configuration file {config} does not define variable'
                  f'`{self.variable}`', always_raise=True)

        return local_dict[self.variable]

    def loadConfig(self):
        with collect_global_errors(and_raise=True):
            return self.load()


class BuildmasterConfigLoader(FileLoader):
    """Loads the buildbot compatible MasterConfig (BuildmasterConfig)"""

    def __init__(self, path, variable='master', inject_globals=None):
        super().__init__(path=path, variable=variable,
                         inject_globals=inject_globals)

    def loadConfig(self):
        with collect_global_errors(and_raise=True):
            return self.load().as_buildbot(self.path)
