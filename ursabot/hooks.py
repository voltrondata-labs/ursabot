from urllib.parse import urlparse

from buildbot.util.logger import Logger
from buildbot.www.hooks.github import GitHubEventHandler
from buildbot.util.httpclientservice import HTTPClientService

from .utils import ensure_deferred
from .commands import CommandError


log = Logger()


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

    def __init__(self, *args, botname='ursabot', comment_handler=None,
                 github_property_whitelist=None, **kwargs):
        assert isinstance(botname, str)
        assert comment_handler is None or callable(comment_handler)
        self.botname = botname
        self.comment_handler = comment_handler

        if not github_property_whitelist:
            # handle_pull_request calls self.extractProperties with
            # payload['pull_request'], so in order to set a title property
            # to the pull_request's title, 'github.title' must be passed to
            # the property whitelist, for the exact implementation see
            # buildbot.changes.github.PullRequestMixin and handle_pull_request
            kwargs['github_property_whitelist'] = ['github.title']

        super().__init__(*args, **kwargs)

    def _client(self, headers=None):
        headers = headers or {}
        headers['User-Agent']: self.botname
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

    async def _get(self, url, headers=None):
        url = urlparse(url)
        client = await self._client(headers=headers)
        response = await client.get(url.path)
        result = await response.json()
        return result

    async def _post(self, url, data, headers=None):
        url = urlparse(url)
        client = await self._client(headers=headers)
        response = await client.post(url.path, json=data)
        result = await response.json()
        log.info(f'POST to {url} with the following result: {result}')
        return result

    @ensure_deferred
    async def handle_issue_comment(self, payload, event):
        # no comment handler is configured, so omit issue/pr comments
        if self.comment_handler is None:
            return [], 'git'

        # only allow users of apache org to submit commands, for more see
        # https://developer.github.com/v4/enum/commentauthorassociation/
        allowed_roles = {'OWNER', 'MEMBER', 'CONTRIBUTOR'}

        mention = f'@{self.botname}'
        repo = payload['repository']
        issue = payload['issue']
        comment = payload['comment']

        async def respond(comment):
            if comment in {'+1', '-1'}:
                url = f"{repo['url']}/comments/{comment['id']}/reactions"
                accept = 'application/vnd.github.squirrel-girl-preview+json'
                await self._post(url, data={'content': comment},
                                 headers={'Accept': accept})
            else:
                await self._post(issue['comments_url'], {'body': comment})

        if payload['sender']['login'] == self.botname:
            # don't respond to itself
            return [], 'git'
        elif payload['action'] not in {'created', 'edited'}:
            # don't respond to comment deletion
            return [], 'git'
        elif payload['comment']['author_association'] not in allowed_roles:
            # don't respond to comments from non-authorized users
            return [], 'git'
        elif not comment['body'].lstrip().startswith(mention):
            # ursabot is not mentioned, nothing to do
            return [], 'git'
        elif 'pull_request' not in issue:
            await respond('Ursabot only listens to pull request comments!')
            return [], 'git'

        try:
            command = comment.split(mention)[-1].lower().strip()
            properties = self.comment_handler(command)
        except CommandError as e:
            await respond(e.message)
            return [], 'git'
        except Exception as e:
            log.error(e)
            return [], 'git'
        else:
            if not properties:
                raise ValueError('`comment_parser` must return properties')

        changes = []
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
            # `event: issue_comment` will be available between the properties,
            # but We still need a way to determine which builders to run, so
            # pass the command property as well and flag the change category as
            # `comment` instead of `pull`
            for change in changes:
                change['category'] = 'comment'
                change['properties'].update(properties)
        except Exception as e:
            log.error(e)
            await respond("I've failed to start builds for this PR")
        else:
            # await respond('+1')
            # TODO(kszucs): consider not responding, send a reaction +1 instead
            await respond("I've successfully started builds for this PR")
        finally:
            return changes, 'git'

    # TODO(kszucs): ursabot might listen on:
    # - handle_commit_comment
    # - handle_pull_request_review
    # - handle_pull_request_review_comment
