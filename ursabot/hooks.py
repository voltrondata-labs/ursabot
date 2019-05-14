from urllib.parse import urlparse

from twisted.python import log
from buildbot.www.hooks.github import GitHubEventHandler
from buildbot.util.httpclientservice import HTTPClientService

from .utils import ensure_deferred

BOTNAME = 'ursabot'


class GithubHook(GitHubEventHandler):
    """Converts github events to changes

    It extends the original implementation for push and pull request events
    with a pull request comment event in order to drive buildbot with gihtub
    comments.
    """

    def _client(self):
        headers = {'User-Agent': 'Buildbot'}
        if self._token:
            headers['Authorization'] = 'token ' + self._token

        # TODO(kszucs): initialize it once?
        return HTTPClientService.getService(
            self.master, self.github_api_endpoint, headers=headers,
            debug=self.debug, verify=self.verify)

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
        log.msg(f'POST to {url} with the following result: {result}')
        return result

    def _parse_command(self, message):
        # TODO(kszucs): make it more sophisticated
        mention = f'@{BOTNAME}'
        if mention in message:
            return message.split(mention)[-1].lower().strip()
        return None

    # TODO(kszucs): only allow users of apache org to submit commands

    @ensure_deferred
    async def handle_issue_comment(self, payload, event):
        issue = payload['issue']
        comments_url = issue['comments_url']
        command = self._parse_command(payload['comment']['body'])

        if payload['sender']['login'] == BOTNAME:
            # don't respond to itself
            return [], 'git'
        elif payload['action'] not in {'created', 'edited'}:
            # don't respond to comment deletion
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
            # handle pull request contains skip-logic and misc message
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

        # event: issue_comment will be available between the properties, but We
        # still need something to determine which builders to run, so pass
        # the command as well
        for change in changes:
            change['properties']['command'] = command

        return changes, 'git'

    # TODO(kszucs):
    # handle_commit_comment d
    # handle_pull_request_review
    # handle_pull_request_review_comment
