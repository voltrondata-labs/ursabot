# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

from buildbot import config
from buildbot.util import NotABranch
from buildbot.plugins import changes
from buildbot.changes import filter

__all__ = ['ChangeFilter', 'GitPoller', 'GitHubPullrequestPoller']


class ChangeFilter(filter.ChangeFilter):
    """Extended with ability to filter on properties"""

    def __init__(self, fn=None, branch=NotABranch, project=None,
                 repository=None, category=None, codebase=None,
                 files=None, properties=None):
        if fn is not None and not callable(fn):
            raise ValueError('ChangeFilter.fn must be callable')

        properties = properties or {}
        if not isinstance(properties, dict):
            raise ValueError('ChangeFilter.properties must be a dictionary')

        # create check tuples for the original arguments
        # branch has a special treatment beacuase of NotABranch
        check_tuples = [
            self._create_check_tuple('branch', branch, default=NotABranch),
            self._create_check_tuple('project', project),
            self._create_check_tuple('repository', repository),
            self._create_check_tuple('category', category),
            self._create_check_tuple('codebase', codebase),
            self._create_check_tuple('files', files)
        ]

        # create check tuples for the properties argument
        check_tuples += [self._create_check_tuple(f'prop:{name}', value)
                         for name, value in properties.items()]

        self.filter_fn = fn
        self.checks = self.createChecks(*check_tuples)

    def _create_check_tuple(self, name, value, default=None):
        # example: (project, project_re, project_fn, "project"),
        if callable(value):
            return (default, None, value, name)
        elif hasattr(value, 'match'):
            return (default, value, None, name)
        else:
            return (value, None, None, name)

    def __repr__(self):
        return f'<ChangeFilter at {id(self)}>'

    def __call__(self, change):
        return self.filter_change(change)


GitPoller = changes.GitPoller


class GitHubPullrequestPoller(changes.GitHubPullrequestPoller):

    def __init__(self, project, name=None, **kwargs):
        try:
            owner, repo = project.split('/')
        except ValueError:
            raise config.error(f'`project` must be in `owner/repo` format '
                               f'instead of {project}')
        name = name or f'GitHubPullrequestPoller: {project}'
        super().__init__(owner, repo, name=name, **kwargs)
