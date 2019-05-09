import re

from twisted.internet import defer
from twisted.python import log

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.util.giturlparse import giturlparse

from buildbot.plugins import reporters, util

from .utils import ensure_deferred


_template = u'''\
<h4>Build status: {{ summary }}</h4>
<p> Worker used: {{ workername }}</p>
{% for step in build['steps'] %}
<p> {{ step['name'] }}: {{ step['result'] }}</p>
{% endfor %}
<p><b> -- The Buildbot</b></p>
'''


class BuilderReporterMixin:

    def __init__(self, *args, builders, **kwargs):
        builder_names = [b.name for b in builders]
        super().__init__(*args, builders=builder_names, **kwargs)


class ZulipMailNotifier(reporters.MailNotifier):

    def __init__(self, zulipaddr, fromaddr, template=None):
        formatter = reporters.MessageFormatter(
            template=template or _template,
            template_type='html',
            wantProperties=True,
            wantSteps=True
        )
        super().__init__(fromaddr=fromaddr, extraRecipients=[zulipaddr],
                         messageFormatter=formatter,
                         sendToInterestedUsers=False)


class GitHubStatusPush(BuilderReporterMixin, reporters.GitHubStatusPush):

    def setDefaults(self, context, startDescription, endDescription):
        # XXX: removed buildbot prefix from the the default context
        self.context = context or Interpolate('%(prop:buildername)s')
        self.startDescription = startDescription or 'Build started.'
        self.endDescription = endDescription or 'Build done.'

    @defer.inlineCallbacks
    def send(self, build):
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
        # XXX: only change - pass `build` to the callbacks
        log.msg(self.__class__.__name__)
        log.msg(props.build)
        props.build = build
        log.msg(props.build)
        log.msg(build)
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
            description = yield props.render(self.endDescription)
        elif self.startDescription:
            state = 'pending'
            description = yield props.render(self.startDescription)
        else:
            return

        context = yield props.render(self.context)

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
            log.msg("[{}] Updating github status: repoOwner={}, repoName={}"
                    .format(self.__class__.__name__, repoOwner, repoName))

        for sourcestamp in sourcestamps:
            sha = sourcestamp['revision']
            try:
                repo_user = repoOwner
                repo_name = repoName
                target_url = build['url']
                response = yield self.createStatus(
                    repo_user=repo_user,
                    repo_name=repo_name,
                    sha=sha,
                    state=state,
                    target_url=target_url,
                    context=context,
                    issue=issue,
                    description=description
                )

                if not self.isStatus2XX(response.code):
                    raise Exception()

                if self.verbose:
                    log.msg(
                        'Updated status with "{state}" for {repoOwner}/'
                        '{repoName} at {sha}, context "{context}", issue '
                        '{issue}.'.format(state=state, repoOwner=repoOwner,
                                          repoName=repoName, sha=sha,
                                          issue=issue, context=context))
            except Exception as e:
                content = yield response.content()
                log.err(
                    e,
                    'Failed to update "{state}" for {repoOwner}/{repoName} '
                    'at {sha}, context "{context}", issue {issue}. '
                    'http {code}, {content}'.format(
                        state=state, repoOwner=repoOwner, repoName=repoName,
                        sha=sha, issue=issue, context=context,
                        code=response.code, content=content))


class GitHubReviewPush(GitHubStatusPush):

    name = 'GitHubReviewPush'

    def path(self, org, repository, issue):
        return '/'.join(['/repos', org, repository, 'pulls', issue, 'reviews'])

    def createStatus(self, repo_user, repo_name, sha, state, target_url=None,
                     context=None, issue=None, description=None):
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

        path = self.path(repo_user, repo_name, issue)
        if self.verbose:
            log.msg(f'Invoking {path} with payload: {payload}')

        return self._http.post(path, json=payload)


@util.renderer
@ensure_deferred
async def end_description(props):
    log.msg(props)
    log.msg(props.build)
    # build = props.build
    #
    # code = build['results']
    # if code in (SUCCESS, WARNINGS):
    #     # render `result` logs
    #     pass
    # elif code in (FAILURE, EXCEPTION, CANCELLED):
    #     pass
    # else:
    #     pass
    #
    # from pprint import pprint
    # pprint(build)
    # log.msg(build)
    return 'Build done.'


class GitHubCommentPush(BuilderReporterMixin, reporters.GitHubCommentPush):

    neededDetails = dict(
        wantProperties=True,
        wantSteps=True,
        wantLogs=True
    )

    def __init__(self, *args, end_description=None, **kwargs):
        kwargs['endDescription'] = end_description
        return super().__init__(*args, **kwargs)

    def setDefaults(self, context, startDescription, endDescription):
        self.context = ''
        self.startDescription = startDescription
        self.endDescription = endDescription or end_description


# async def get_step_results(data, buildername, buildnumber):
#     # query the logs belonging to the last step of the build, so keep the
#     # result in the final step!
#     path = ('builders', buildername, 'builds', buildnumber, 'steps')
#     steps = await data.get(path)
#
#     results = []
#     for step in steps:
#         id = step['stepid']
#         name = step['name']
#         code = step['results']
#         result = util.Results[code]
#
#         if code == util.results.SUCCESS:
#             # if the step has succeeded then try to retrieve the result log
#             result_content = await data.get(('steps', id, 'logs', 'result'))
#         else:
#             # otherwise collect all of the logs
#             logs = await data.get(('steps', stepid, 'logs'))
#             content = [f'Step: {name} Result: {result}' for log in logs]
#
#         results.append({
#             'id': id,
#             'name': name,
#             'code': code,
#             'result': result,
#             'rcontent': contentx
#         })
#
#     return results
