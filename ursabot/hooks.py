from urllib.parse import urlparse

from buildbot.util.logger import Logger
from buildbot.www.hooks.github import GitHubEventHandler
from buildbot.util.httpclientservice import HTTPClientService

from .utils import ensure_deferred


log = Logger()

# TODO(kszucs): make it configurable
BOTNAME = 'ursabot'


class GithubHook(GitHubEventHandler):
    """Converts github events to changes

    It extends the original implementation for push and pull request events
    with a pull request comment event in order to drive buildbot with gihtub
    comments.

    Github hook creates 4 kinds of changes, distinguishable by their category
    field:

    None: This change is a push to a branch.
        Use ursabot.changes.ChangeFilter(
            category=None,
            repository="http://github.com/<org>/<project>"
        )
    'tag': This change is a push to a tag.
        Use ursabot.changes.ChangeFilter(
            category='tag',
            repository="http://github.com/<org>/<project>"
        )
    'pull': This change is from a pull-request creation or update.
        Use ursabot.changes.ChangeFilter(
            category='pull',
            repository="http://github.com/<org>/<project>"
        )
        In this case, the GitHub step must be used instead of the standard Git
        in order to be able to pull GitHub’s magic refs (refs/pull/<id>/merge).
        With this method, the GitHub step will always checkout the branch
        merged with latest master. This allows to test the result of the merge
        instead of just the source branch.
        Note that you can use the GitHub for all categories of event.
    'comment': This change is from a pull-request comment requested by a
        comment like: `@ursabot <command>`. Two special properties will be set
        `event: issue_comment` and `command: <command>`.
        Use ursabot.changes.ChangeFilter(
            category='comment',
            repository="http://github.com/<org>/<project>"
        )
        Optionally filter with properties: ursabot.changes.ChangeFilter(
            category='comment',
            repository="http://github.com/<org>/<project>",
            properties={
                'event': 'issue_comment',
                'command': '<command>'
            }
        )
    """

    def __init__(self, *args, **kwargs):
        if not kwargs.get('github_property_whitelist'):
            # handle_pull_request calls self.extractProperties with
            # payload['pull_request'], so in order to set a title property
            # to the pull_request's title, 'github.title' must be passed to
            # the property whitelist, for the exact implementation see
            # buildbot.changes.github.PullRequestMixin and handle_pull_request
            kwargs['github_property_whitelist'] = ['github.title']
        super().__init__(*args, **kwargs)

    def _client(self):
        headers = {'User-Agent': 'Buildbot'}
        if self._token:
            headers['Authorization'] = 'token ' + self._token

        # TODO(kszucs): initialize it once?
        return HTTPClientService.getService(
            self.master,
            self.github_api_endpoint,
            headers=headers,
            debug=self.debug,
            verify=self.verify
        )

    async def _get(self, url):
        url = urlparse(url)
        client = await self._client()
        response = await client.get(url.path)
        result = await response.json()
        return result

    async def _post(self, url, data):
        url = urlparse(url)
        client = await self._client()
        response = await client.post(url.path, json=data)
        result = await response.json()
        log.info(f'POST to {url} with the following result: {result}')
        return result

    def _parse_command(self, message):
        # TODO(kszucs): make it more sophisticated
        mention = f'@{BOTNAME}'
        if mention in message:
            return message.split(mention)[-1].lower().strip()
        return None

    @ensure_deferred
    async def handle_issue_comment(self, payload, event):
        issue = payload['issue']
        comments_url = issue['comments_url']
        command = self._parse_command(payload['comment']['body'])

        # only allow users of apache org to submit commands, for more see
        # https://developer.github.com/v4/enum/commentauthorassociation/
        allowed_roles = {'OWNER', 'MEMBER', 'CONTRIBUTOR'}

        if payload['sender']['login'] == BOTNAME:
            # don't respond to itself
            return [], 'git'
        elif payload['action'] not in {'created', 'edited'}:
            # don't respond to comment deletion
            return [], 'git'
        elif payload['comment']['author_association'] not in allowed_roles:
            # don't respond to comments from non-authorized users
            return [], 'git'
        elif command is None:
            # ursabot is not mentioned, nothing to do
            return [], 'git'
        elif command in ('build', 'benchmark'):
            if 'pull_request' not in issue:
                message = 'Ursabot only listens to pull request comments!'
                await self._post(comments_url, {'body': message})
                return [], 'git'
        else:
            message = f'Unknown command "{command}"'
            await self._post(comments_url, {'body': message})
            return [], 'git'

        try:
            pull_request = await self._get(issue['pull_request']['url'])
            # handle_pull_request contains pull request specific logic
            changes, _ = await self.handle_pull_request({
                'action': 'synchronize',
                'sender': payload['sender'],
                'repository': payload['repository'],
                'pull_request': pull_request,
                'number': pull_request['number'],
            }, event)
        except Exception as e:
            message = "I've failed to start builds for this PR"
            await self._post(comments_url, {'body': message})
            raise e

        # TODO(kszucs): consider not responding
        message = "I've successfully started builds for this PR"
        await self._post(comments_url, {'body': message})

        for change in changes:
            # `event: issue_comment` will be available between the properties,
            # but We still need a way to determine which builders to run, so
            # pass the command property as well and flag the change category as
            # `comment` instead of `pull`
            change['category'] = 'comment'
            change['properties']['command'] = command

        return changes, 'git'

    # TODO(kszucs): ursabot might listen on:
    # - handle_commit_comment
    # - handle_pull_request_review
    # - handle_pull_request_review_comment
