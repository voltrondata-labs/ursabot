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
import traceback
from pathlib import Path

import toolz
from twisted.python.compat import execfile
from buildbot.config import ConfigErrors, error
from buildbot.util.logger import Logger


log = Logger()


class ProjectConfig:

    def __init__(self, name, workers, builders, schedulers, pollers=None,
                 reporters=None, images=None):
        self.name = name
        self.workers = workers
        self.builders = builders
        self.schedulers = schedulers
        self.images = images or []
        self.pollers = pollers or []
        self.reporters = reporters or []

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.name}>'


def MasterConfig(title, url, webui_port, worker_port, projects,
                 database_url=None, auth=None, authz=None, change_hook=None,
                 secret_providers=None):
    """Returns with the dictionary that the buildmaster pays attention to."""

    def component(key):
        return list(toolz.concat(getattr(p, key) for p in projects))

    if change_hook is None:
        hook_dialect_config = {}
    else:
        hook_dialect_config = change_hook._as_hook_dialect_config()

    buildmaster_config = {
        'buildbotNetUsageData': None,
        'title': title,
        'titleURL': url,
        'buildbotURL': url,
        'workers': component('workers'),
        'builders': component('builders'),
        'schedulers': component('schedulers'),
        'services': component('reporters'),
        'change_source': component('pollers'),
        'secretsProviders': secret_providers or [],
        'protocols': {'pb': {'port': worker_port}},
        'db': {'db_url': database_url},
        'www': {
            'port': webui_port,
            'change_hook_dialects': hook_dialect_config,
            'plugins': {
                'waterfall_view': {},
                'console_view': {},
                'grid_view': {}
            }
        }
    }

    # buildbot raises errors for None or empty dict values so only set of they
    # are passed
    if auth is not None:
        buildmaster_config['www']['auth'] = auth
    if authz is not None:
        buildmaster_config['www']['authz'] = authz

    return buildmaster_config


def load_variable(config, variable):
    """Load variable from python file

    License note:
        It is a reimplementation based on the parent GitHubStatusPush
        from the original buildbot implementation.
    """

    config = Path(config).absolute()
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
        'basedir': basedir.expanduser(),
        '__file__': config
    }

    # TODO(kszucs): ask @pitrou about how to fool python to use basedir
    #               as the base of the relative paths used within the loaded
    #               python file
    old_sys_path = sys.path[:]
    sys.path.append(str(basedir))
    try:
        try:
            execfile(config, local_dict)
        except ConfigErrors:
            raise
        except SyntaxError:
            exc = traceback.format_exc()
            error(
                f'encountered a SyntaxError while parsing config file:\n{exc}',
                always_raise=True
            )
        except Exception:
            exc = traceback.format_exc()
            msg = (f'error while parsing config file: {exc} '
                   f'(traceback in logfile)')
            error(msg, always_raise=True)
    finally:
        sys.path[:] = old_sys_path

    if variable not in local_dict:
        msg = (f"Configuration file {config} does not define variable"
               f"'{variable}'")
        error(msg, always_raise=True)

    return config, local_dict[variable]
