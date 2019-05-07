from buildbot.plugins import reporters
from twisted.python import log


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
    pass


class GitHubCommentPush(BuilderReporterMixin, reporters.GitHubCommentPush):
    pass


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
