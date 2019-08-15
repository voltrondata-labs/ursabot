# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.
#
# This file contains function or sections of code that are marked as being
# derivative works of Buildbot. The above license only applies to code that
# is not marked as such.

import re
import collections

from buildbot import config
from buildbot.util.logger import Logger
from buildbot.util.giturlparse import giturlparse
from buildbot.reporters.http import HttpStatusPushBase
from buildbot.interfaces import IRenderable
from buildbot.process.properties import Properties, Interpolate, renderer
from buildbot.process.results import (Results, CANCELLED, EXCEPTION, FAILURE,
                                      RETRY, SKIPPED, SUCCESS, WARNINGS)

from .utils import ensure_deferred, HTTPClientService, GithubClientService
from .builders import Builder
from .formatters import Formatter, MarkdownFormatter

__all__ = [
    'HttpStatusPush',
    'GitHubReporter',
    'GitHubStatusPush',
    'GitHubReviewPush',
    'GitHubCommentPush',
    'ZulipStatusPush'
]

log = Logger()

# `started` doesn't belong to results
# a build is started if build[complete] is False
_statuses = frozenset(['started'] + Results)


class HttpStatusPush(HttpStatusPushBase):
    """Makes possible to configure whether to send reports on started builds"""

    def __init__(self, baseURL, headers=None, auth=None, builders=None,
                 verbose=False, report_on=None, dont_report_on=None,
                 debug=False, verify=None, **kwargs):
        headers = headers or {'User-Agent': 'Ursabot'}

        if builders is None:
            builder_names = None
        else:
            builder_names = []
            for b in builders:
                if isinstance(b, Builder):
                    builder_names.append(b.name)
                elif isinstance(b, str):
                    builder_names.append(b)
                else:
                    config.error('`builders` must be a list of strings or '
                                 'a list of BuilderConfig objects')

        super().__init__(baseURL=baseURL, headers=headers, auth=auth,
                         report_on=report_on, dont_report_on=dont_report_on,
                         builders=builder_names, verbose=verbose, debug=debug,
                         verify=verify, **kwargs)

    def checkConfig(self, baseURL, headers, report_on, dont_report_on,
                    **kwargs):
        if not isinstance(baseURL, str):
            config.error('`baseURL` must be an instrance of str')
        if not isinstance(headers, dict):
            config.error('`headers` must be an instrance of dict')

        # validating report on events sets
        args = [('report_on', report_on),
                ('dont_report_on', dont_report_on)]
        for name, value in args:
            if value is None:
                continue
            elif not isinstance(value, collections.abc.Set):
                config.error(f'`{name}` argument must be an instanse of set')
            elif not value.issubset(_statuses):
                invalids = value - _statuses
                config.error(f'`{name}` contains invalid elements: {invalids}')

        if report_on and dont_report_on:
            config.error('Ambiguously both `report_on` and `dont_report_on` '
                         'are defined, please pass either `report_on` or '
                         '`dont_report_on`')

        # validate the remaining arguments
        super().checkConfig(**kwargs)

    @ensure_deferred
    async def reconfigService(self, verbose, report_on, dont_report_on,
                              **kwargs):
        await super().reconfigService(**kwargs)
        await self.reconfigClient(**kwargs)
        self.verbose = verbose
        self.report_on = (report_on or _statuses) - (dont_report_on or set())

    async def reconfigClient(self, baseURL, headers, auth, debug, verify,
                             **kwargs):
        self._http = await HTTPClientService.getService(
            self.master,
            baseURL,
            auth=auth,
            headers=headers,
            debug=debug,
            verify=verify
        )

    def filterBuilds(self, build):
        status = Results[build['results']] if build['complete'] else 'started'
        if status not in self.report_on:
            return False
        return super().filterBuilds(build)

    @ensure_deferred
    async def send(self, build):
        # License note:
        #     It is a reimplementation based on the parent GitHubStatusPush
        #     from the original buildbot implementation.
        #
        # We must propagate the build down to the renderer callbacks
        # (endDescription, startDescription), otherwise there is no way to
        # retrieve the build and its logs.
        #
        # Only `buildername` and `builnumber` properties are set, but
        # data.get(('builders', buildername, 'builds', buildnumber)) raises
        # for non-alphanumerical builder name:
        #    Invalid path: builders/Ursabot Python 3.7/builds/2
        # So the official[quiet twisted] example wouldn't work:
        #    http://docs.buildbot.net/2.3.0/full.html#githubcommentpush

        cls = self.__class__.__name__

        build_number = build['number']
        builder_name = build['builder']['name']
        sourcestamps = build['buildset'].get('sourcestamps', [])
        properties = Properties.fromDict(build['properties'])

        for sourcestamp in sourcestamps:
            project = sourcestamp.get('project')
            repository = sourcestamp.get('repository')

            if self.verbose:
                log.info(
                    f'Triggering {cls}.report() for project {project}, '
                    f'repository {repository}, builder {builder_name}, '
                    f'build number {build_number}'
                )

            try:
                response = await self.report(build, sourcestamp, properties)
            except Exception as e:
                log.error(e)
                raise e

            # report() can return None to skip reporting
            if response is None:
                continue

            if not self.isStatus2XX(response.code):
                content = await response.content()
                e = Exception(
                    f'Failed to execute http API call in {cls}.report() for '
                    f'repository {repository}, builder {builder_name}, build '
                    f'number {build_number} with error code {response.code} '
                    f'and response "{content}"'
                )
                log.error(e)
                raise e

            if self.verbose:
                log.info(
                    f'Successful report {cls}.report() for repository '
                    f'{repository}, builder {builder_name}, build number '
                    f'{build_number}'
                )


class GitHubReporter(HttpStatusPush):
    """Base class for reporters interacting with GitHub's API"""

    neededDetails = dict(
        wantProperties=True
    )

    def __init__(self, tokens, baseURL=None, formatter=None, **kwargs):
        # support for self-hosted github enterprise
        if baseURL is None:
            baseURL = 'https://api.github.com'
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]
        formatter = formatter or Formatter()
        super().__init__(tokens=tokens, baseURL=baseURL, formatter=formatter,
                         **kwargs)

    def checkConfig(self, formatter=None, **kwargs):
        if not isinstance(formatter, (type(None), Formatter)):
            config.error('`formatter` must be an instance of '
                         'ursabot.formatters.Formatter')
        super().checkConfig(**kwargs)

    @ensure_deferred
    async def reconfigService(self, formatter, **kwargs):
        await super().reconfigService(**kwargs)
        self.formatter = formatter

    async def reconfigClient(self, baseURL, headers, tokens, auth, debug,
                             verify, **kwargs):
        tokens = [await self.renderSecrets(token) for token in tokens]
        self._http = await GithubClientService.getService(
            self.master,
            baseURL,
            tokens=tokens,
            auth=auth,
            headers=headers,
            debug=debug,
            verify=verify
        )

    def _extract_github_params(self, sourcestamp, branch=None):
        """Parses parameters required to by github

        License note:
            Contains copied parts from the original buildbot implementation.
        """
        # branch is updated by the checkoutstep, required for PRs
        branch = branch or sourcestamp['branch']
        project = sourcestamp['project']
        repo = sourcestamp['repository']
        sha = sourcestamp['revision']

        # determine whether the branch refers to a PR
        m = re.search(r'refs/pull/([0-9]*)/merge', branch)
        if m:
            issue = m.group(1)
        else:
            issue = None

        if '/' in project:
            repo_owner, repo_name = project.split('/')
        else:
            giturl = giturlparse(repo)
            repo_owner, repo_name = giturl.owner, giturl.repo

        return dict(
            sha=sha,
            repo=repo,
            branch=branch,
            issue=issue,
            repo_owner=repo_owner,
            repo_name=repo_name
        )

    @ensure_deferred
    async def report(self, build, sourcestamp, properties):
        raise NotImplementedError()


class GitHubStatusPush(GitHubReporter):
    """Interacts with GitHub's status APIs

    See https://developer.github.com/v3/repos/statuses
    """

    name = 'GitHubStatusPush'

    def __init__(self, *args, context=None, **kwargs):
        context = context or Interpolate('ursabot/%(prop:buildername)s')
        super().__init__(*args, context=context, **kwargs)

    @ensure_deferred
    async def reconfigService(self, context=None, **kwargs):
        await super().reconfigService(**kwargs)
        self.context = context

    def _state_for(self, build):
        """Maps buildbot results to github statuses

        License note:
            Contains copied parts from the original buildbot implementation.
        """
        statuses = {
            SUCCESS: 'success',
            WARNINGS: 'success',
            SKIPPED: 'success',
            EXCEPTION: 'error',
            CANCELLED: 'error',
            FAILURE: 'failure',
            RETRY: 'pending'
        }

        if build['complete']:
            result = build['results']
            return statuses.get(result, 'error')
        else:
            return 'pending'

    @ensure_deferred
    async def report(self, build, sourcestamp, properties):
        params = self._extract_github_params(sourcestamp,
                                             branch=properties['branch'])
        payload = {
            'target_url': build['url'],
            'state': self._state_for(build),
            'context': await properties.render(self.context),
            'description': await self.formatter.render(build, self.master)
        }
        urlpath = '/'.join([
            '/repos',
            params['repo_owner'],
            params['repo_name'],
            'statuses',
            params['sha']
        ])
        if self.verbose:
            log.info(f'Invoking {urlpath} with payload: {payload}')

        return await self._http.post(urlpath, json=payload)


class GitHubReviewPush(GitHubReporter):
    """Mimics the status API functionality with pull-request reviews

    Prefer GitHubStatusPush over GitHubReviewPush, but the former requires
    a token with `repo:status` scope checked and write access to the
    repository, whereas the review push doesn't require any special permission.
    """

    name = 'GitHubReviewPush'

    def _event_for(self, build):
        # maps buildbot results to github review events, blank means pending
        events = {
            SUCCESS: 'APPROVE',
            WARNINGS: 'APPROVE',
            SKIPPED: 'APPROVE',
            EXCEPTION: 'REQUEST_CHANGES',
            CANCELLED: 'REQUEST_CHANGES',
            FAILURE: 'REQUEST_CHANGES',
            RETRY: 'PENDING'
        }

        if build['complete']:
            result = build['results']
            return events.get(result, 'REQUEST_CHANGES')
        else:
            return 'PENDING'

    @ensure_deferred
    async def report(self, build, sourcestamp, properties):
        params = self._extract_github_params(sourcestamp,
                                             branch=properties['branch'])
        if not params.get('issue'):
            raise ValueError('GitHub review push requires a pull request, but '
                             'the branch is not a pull request reference: ' +
                             params['branch'])

        payload = {
            'commit_id': params['sha'],
            'event': self._event_for(build),
            'body': await self.formatter.render(build, master=self.master)
        }
        urlpath = '/'.join([
            '/repos',
            params['repo_owner'],
            params['repo_name'],
            'pulls',
            params['issue'],
            'reviews'
        ])
        if self.verbose:
            log.info(f'Invoking {urlpath} with payload: {payload}')

        return await self._http.post(urlpath, json=payload)


class GitHubCommentPush(GitHubReporter):
    """Report as a GitHub comment to the pull-request

    Pass a ursabot.formatters.Formatter instance for custom comment formatting.
    """

    name = 'GitHubCommentPush'

    # the formatter will receive all of the following details
    # as nested dictionaries under the build variable
    neededDetails = dict(
        wantProperties=True,
        wantSteps=True,
        wantLogs=True
    )

    def __init__(self, formatter=None, **kwargs):
        formatter = formatter or MarkdownFormatter()
        super().__init__(formatter=formatter, **kwargs)

    @ensure_deferred
    async def report(self, build, sourcestamp, properties):
        # License note:
        #     Contains copied parts from the original buildbot implementation.
        params = self._extract_github_params(sourcestamp,
                                             branch=properties['branch'])
        payload = {
            'body': await self.formatter.render(build, master=self.master)
        }
        urlpath = '/'.join([
            '/repos',
            params['repo_owner'],
            params['repo_name'],
            'issues',
            params['issue'],
            'comments'
        ])
        return await self._http.post(urlpath, json=payload)


@renderer
def _topic_default(props):
    project = props['project']
    builder = '{} # {}'.format(props['buildername'], props['buildnumber'])

    if 'github.title' in props:
        # set by ursabot.hooks.GithubHoook in case of pull requests
        # title is usually more descriptive than the branch's name
        branch = props['github.title']
    else:
        branch = props['branch']

    title = branch or builder
    if project:
        return f'{project} @ {title}'
    else:
        return title


class ZulipStatusPush(HttpStatusPush):

    name = 'ZulipStatusPush'
    neededDetails = dict(
        wantProperties=True,
        wantSteps=True,
        wantLogs=True
    )

    def __init__(self, organization, bot, apikey, stream, topic=None,
                 formatter=None, **kwargs):
        auth = (bot, apikey)
        baseURL = f'https://{organization}.zulipchat.com/api/v1'
        topic = topic or _topic_default
        formatter = formatter or Formatter()
        super().__init__(baseURL=baseURL, auth=auth, stream=stream,
                         topic=topic, formatter=formatter, **kwargs)

    def checkConfig(self, stream, topic, formatter, **kwargs):
        super().checkConfig(**kwargs)
        if not isinstance(stream, str):
            config.error('`stream` must be an instance of str')
        if not (isinstance(topic, str) or IRenderable.providedBy(topic)):
            config.error('`topic` must be a renderable or an instance of str')
        if not isinstance(formatter, (type(None), Formatter)):
            config.error('`formatter` must be an instance of '
                         'ursabot.formatters.Formatter')
        super().checkConfig(**kwargs)

    @ensure_deferred
    async def reconfigService(self, stream, topic, formatter, **kwargs):
        await super().reconfigService(**kwargs)
        self.topic = topic
        self.stream = stream
        self.formatter = formatter

    @ensure_deferred
    async def report(self, build, sourcestamp, properties):
        payload = {
            'type': 'stream',
            'to': self.stream,
            'subject': await properties.render(self.topic),  # zulip topic
            'content': await self.formatter.render(build, self.master)
        }
        urlpath = '/messages'
        if self.verbose:
            log.info(f'Invoking {urlpath} with payload: {payload}')

        return await self._http.post(urlpath, data=payload)
