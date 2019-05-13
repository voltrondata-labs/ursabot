import re

from twisted.python import log
from buildbot.plugins import reporters
from buildbot.reporters import http
from buildbot.util.giturlparse import giturlparse
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.process.properties import Properties, Interpolate
from buildbot.process.results import (CANCELLED, EXCEPTION, FAILURE, RETRY,
                                      SKIPPED, SUCCESS, WARNINGS)

from .utils import ensure_deferred
from .formatters import GitHubCommentFormatter


_template = u'''\
<h4>Build status: {{ summary }}</h4>
<p> Worker used: {{ workername }}</p>
{% for step in build['steps'] %}
<p> {{ step['name'] }}: {{ step['result'] }}</p>
{% endfor %}
<p><b> -- The Buildbot</b></p>
'''


class ZulipMailNotifier(reporters.MailNotifier):

    def __init__(self, zulipaddr, fromaddr, template=None, builders=None):
        formatter = reporters.MessageFormatter(
            template=template or _template,
            template_type='html',
            wantProperties=True,
            wantSteps=True
        )
        if builders is not None:
            builders = [b.name for b in builders]
        super().__init__(fromaddr=fromaddr, extraRecipients=[zulipaddr],
                         messageFormatter=formatter, builders=builders,
                         sendToInterestedUsers=False)


# TODO(kszucs): buildset handling is not yet implemented in HttpStatusPush,
# so We can only handle single builds. We need to fetch and group builds to
# buildsets manually on long term.
class GitHubReporterBase(http.HttpStatusPushBase):

    neededDetails = dict(
        wantProperties=True
    )

    def __init__(self, *args, builders=None, start_description=None,
                 end_description=None, **kwargs):
        if builders is not None:
            kwargs['builders'] = [b.name for b in builders]
        return super().__init__(*args, **kwargs)

    @ensure_deferred
    async def reconfigService(self, token, baseURL=None, verbose=False,
                              **kwargs):
        await super().reconfigService(**kwargs)

        # support for self-hosted github enterprise
        if baseURL is None:
            baseURL = 'https://api.github.com'
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]

        token = await self.renderSecrets(token)
        headers = {
            'Authorization': 'token ' + token,
            'User-Agent': 'Buildbot'
        }

        self._http = await HTTPClientService.getService(
            self.master,
            baseURL,
            headers=headers,
            debug=self.debug,
            verify=self.verify
        )
        self.verbose = verbose

    def _github_params(self, sourcestamp, branch=None):
        # branch is updated by the checkoutstep, required for PRs
        branch = branch or sourcestamp['branch']
        project = sourcestamp['project']
        repo = sourcestamp['repository']
        sha = sourcestamp['revision']

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

        return dict(repo=repo, branch=branch, sha=sha, issue=issue,
                    repo_owner=repo_owner, repo_name=repo_name)

    @ensure_deferred
    async def send(self, build):
        # XXX: the whole method is reimplemented based on the parent
        # GitHubStatusPush implementation, because We must propagate the build
        # down to the renderer callbacks (endDescription, startDescription),
        # otherwise there is no way to retrieve the build and its logs.
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
        branch = properties['branch']

        for sourcestamp in sourcestamps:
            github_params = self._github_params(sourcestamp, branch=branch)
            repo = github_params['repo']

            if self.verbose:
                log.msg(
                    f'Triggering {cls}.report() for repository {repo}, '
                    f'builder {builder_name}, build number {build_number}'
                )

            try:
                response = await self.report(build, properties, github_params)
            except Exception as e:
                log.err(e)
                raise e

            # report() can return None to skip reporting
            if response is None:
                continue

            if not self.isStatus2XX(response.code):
                content = await response.content()
                e = Exception(
                    f'Failed to execute github API call in {cls}.report() '
                    f'for repository {repo}, builder {builder_name}, build '
                    f'number {build_number} with error code {response.code} '
                    f'and response "{content}"'
                )
                log.err(e)
                raise e

            if self.verbose:
                log.msg(
                    f'Successful report {cls}.report() for repository {repo}, '
                    f'builder {builder_name}, build number {build_number}'
                )

    @ensure_deferred
    async def report(self, build, properties, github_params):
        raise NotImplementedError()


class GitHubStatusPush(GitHubReporterBase):

    name = 'GitHubStatusPush'

    @ensure_deferred
    async def reconfigService(self, context=None, **kwargs):
        await super().reconfigService(**kwargs)
        if context is None:
            self.context = Interpolate('buildbot/%(prop:buildername)s')
        else:
            self.context = context

    def _state_for(self, build):
        # maps buildbot results to github statuses
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
    async def report(self, build, properties, github_params):
        state = self._state_for(build)
        context = await properties.render(self.context)
        description = 'Build started.' if state == 'pending' else 'Build done.'

        payload = {
            'state': state,
            'context': context,
            'description': description,
            'target_url': build['url']
        }
        urlpath = '/'.join([
            '/repos',
            github_params['repo_owner'],
            github_params['repo_name'],
            'statuses',
            github_params['sha']
        ])
        if self.verbose:
            log.msg(f'Invoking {urlpath} with payload: {payload}')

        return await self._http.post(urlpath, json=payload)


class GitHubReviewPush(GitHubReporterBase):

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
            RETRY: ''
        }

        if build['complete']:
            result = build['results']
            return events.get(result, 'REQUEST_CHANGES')
        else:
            return ''

    @ensure_deferred
    async def report(self, build, properties, github_params):
        if not github_params.get('issue'):
            raise ValueError('GitHub review push requires a pull request, but '
                             'the branch is not a pull request reference: ' +
                             github_params['branch'])

        payload = {
            'event': self._event_for(build),
            'commit_id': github_params['sha']
        }
        urlpath = '/'.join([
            '/repos',
            github_params['repo_owner'],
            github_params['repo_name'],
            'pulls',
            github_params['issue'],
            'reviews'
        ])
        if self.verbose:
            log.msg(f'Invoking {urlpath} with payload: {payload}')

        return await self._http.post(urlpath, json=payload)


class GitHubCommentPush(GitHubReporterBase):

    name = 'GitHubCommentPush'
    neededDetails = dict(
        wantProperties=True,
        wantSteps=True,
        wantLogs=True
    )

    @ensure_deferred
    async def reconfigService(self, formatter=None, **kwargs):
        await super().reconfigService(**kwargs)
        self.formatter = formatter or GitHubCommentFormatter()

    @ensure_deferred
    async def report(self, build, properties, github_params):
        if not build['complete']:
            return

        payload = {
            'body': await self.formatter.render(build, master=self.master)
        }
        urlpath = '/'.join([
            '/repos',
            github_params['repo_owner'],
            github_params['repo_name'],
            'issues',
            github_params['issue'],
            'comments'
        ])
        return await self._http.post(urlpath, json=payload)
