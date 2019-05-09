import re

from twisted.python import log

from buildbot.plugins import reporters
from buildbot.util.giturlparse import giturlparse
from buildbot.process.properties import Properties
from buildbot.process.results import (CANCELLED, EXCEPTION, FAILURE, RETRY,
                                      SKIPPED, SUCCESS, WARNINGS)

from .utils import ensure_deferred


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


class GitHubStatusPush(reporters.GitHubStatusPush):

    def __init__(self, *args, builders=None, start_description=None,
                 end_description=None, **kwargs):
        kwargs['endDescription'] = end_description
        kwargs['startDescription'] = start_description
        if builders is not None:
            kwargs['builders'] = [b.name for b in builders]
        return super().__init__(*args, **kwargs)

    @ensure_deferred
    async def send(self, build):
        # XXX: the whole method is copy & pasted from the parent
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

        props = Properties.fromDict(build['properties'])
        # XXX: pass `build` to the callbacks
        props.build = build
        props.master = self.master

        if build['complete']:
            state = {
                SUCCESS: 'success',
                WARNINGS: 'success',
                FAILURE: 'failure',
                SKIPPED: 'success',
                EXCEPTION: 'error',
                RETRY: 'pending',
                CANCELLED: 'error'
            }.get(build['results'], 'error')
            # TODO(kszucs): use formatters instead of interpolate, but keep
            # compatibility with createStatus
            description = await props.render(self.endDescription)
        elif self.startDescription:
            state = 'pending'
            description = await props.render(self.startDescription)
        else:
            return

        context = await props.render(self.context)
        sourcestamps = build['buildset'].get('sourcestamps')
        if not sourcestamps or not sourcestamps[0]:
            return

        project = sourcestamps[0]['project']
        branch = props['branch']
        m = re.search(r"refs/pull/([0-9]*)/merge", branch)
        if m:
            issue = m.group(1)
        else:
            issue = None

        if "/" in project:
            repoOwner, repoName = project.split('/')
        else:
            giturl = giturlparse(sourcestamps[0]['repository'])
            repoOwner = giturl.owner
            repoName = giturl.repo

        if self.verbose:
            # XXX: extra log context class
            log.msg('[{}] Updating github status: repoOwner={}, repoName={}'
                    .format(self.__class__.__name__, repoOwner, repoName))

        for sourcestamp in sourcestamps:
            # XXX: pick the first sourcestamp only?
            sha = sourcestamp['revision']
            repo_user = repoOwner
            repo_name = repoName
            target_url = build['url']

            # XXX: refactored error handling
            try:
                response = await self.createStatus(
                    # TODO: pass master
                    repo_user=repo_user,
                    repo_name=repo_name,
                    sha=sha,
                    state=state,
                    target_url=target_url,
                    context=context,
                    issue=issue,
                    description=description
                )
            except Exception as exc:
                log.err(exc)
                raise

            if response is None:
                continue

            if not self.isStatus2XX(response.code):
                content = await response.content()
                exc = Exception(
                    f'Failed to update "{state}" for {repoOwner}/{repoName} '
                    f'at {sha}, context "{context}", issue {issue}. '
                    f'http {response.code}, {content}'
                )
                log.err(exc)
                raise exc

            if self.verbose:
                log.msg(f'Updated status with "{state}" for {repoOwner}/'
                        f'{repoName} at {sha}, context "{context}", issue '
                        f'{issue}.')


class GitHubReviewPush(GitHubStatusPush):

    name = 'GitHubReviewPush'

    @ensure_deferred
    async def createStatus(self, repo_user, repo_name, sha, state,
                           target_url=None, context=None, issue=None,
                           description=None):
        # Do not create a pending review as it induce more problem.
        if state == 'pending':
            return None

        # Convert state into the expected review status.
        status_mapping = {
            'success': 'APPROVE',
            # Unsure how to deal with buildbot errors
            'error': 'COMMENT',
            'failure': 'REQUEST_CHANGES',
        }
        payload = {
            'event': status_mapping.get(state),
            'body': description
        }

        if sha:
            # defaults to the most recent commit in the pull request when unset
            payload['commit_id'] = sha

        path = '/'.join(['/repos', repo_user, repo_name, 'pulls', issue,
                         'reviews'])
        if self.verbose:
            log.msg(f'Invoking {path} with payload: {payload}')

        return await self._http.post(path, json=payload)


class GitHubCommentPush(GitHubStatusPush):

    name = 'GitHubCommentPush'
    neededDetails = dict(
        wantProperties=True,
        wantSteps=True,
        wantLogs=True
    )

    @ensure_deferred
    async def reconfigService(self, comment_formatter=None, **kwargs):
        await super().reconfigService(**kwargs)
        self.comment_formatter = comment_formatter

    @ensure_deferred
    async def createStatus(self, repo_user, repo_name, sha, state,
                           target_url=None, context=None, issue=None,
                           description=None):
        # if self.comment_formatter is not None:
        #     comment = self.comment_formatter.renderMessage(ctx)
        # else:
        #     comment = description

        payload = {'body': description}
        path = '/'.join(['/repos', repo_user, repo_name, 'issues', issue,
                         'comments'])
        return await self._http.post(path, json=payload)
