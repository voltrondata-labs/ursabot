# Copyright 2019 RStudio, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from buildbot import config
from buildbot.util import NotABranch
from buildbot.plugins import changes
from buildbot.changes import filter


class ChangeFilter(filter.ChangeFilter):
    """Extended with ability to filter on properties"""

    def __init__(self, fn=None, branch=NotABranch, project=None,
                 repository=None, category=None, codebase=None,
                 properties=None):
        if fn is not None and not callable(fn):
            raise ValueError('ChangeFilter.fn must be callable')

        properties = properties or {}
        if not isinstance(properties, dict):
            raise ValueError('ChangeFilter.properties must be a dictionary')

        # create check tuples for the original arguments
        # branch has a special treatment beacuase of NotABranch
        checks = [
            self._create_check_tuple('branch', branch, default=NotABranch),
            self._create_check_tuple('project', project),
            self._create_check_tuple('repository', repository),
            self._create_check_tuple('category', category),
            self._create_check_tuple('codebase', codebase)
        ]

        # create check tuples for the properties argument
        checks += [self._create_check_tuple(f'prop:{name}', value)
                   for name, value in properties.items()]

        self.filter_fn = fn
        self.checks = self.createChecks(*checks)

    def _create_check_tuple(self, name, value, default=None):
        # sample: (project, project_re, project_fn, "project"),
        if callable(value):
            return (default, None, value, name)
        elif hasattr(value, 'match'):
            return (default, value, None, name)
        else:
            return (value, None, None, name)


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
