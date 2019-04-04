from urllib.parse import urlparse

from twisted.python import log
from twisted.internet import defer

from buildbot.www.hooks.github import GitHubEventHandler
from buildbot.util.httpclientservice import HTTPClientService


BOTNAME = 'ursabot'


class GithubHook(GitHubEventHandler):

    def _client(self):
        headers = {'User-Agent': 'Buildbot'}
        if self._token:
            headers['Authorization'] = 'token ' + self._token

        # TODO(kszucs): initialize it once?
        return HTTPClientService.getService(
            self.master, self.github_api_endpoint, headers=headers,
            debug=self.debug, verify=self.verify)

    @defer.inlineCallbacks
    def _get(self, url):
        url = urlparse(url)
        client = yield self._client()
        response = yield client.get(url.path)
        result = yield response.json()
        return result

    @defer.inlineCallbacks
    def _post(self, url, data):
        url = urlparse(url)
        client = yield self._client()
        response = yield client.post(url.path, json=data)
        result = yield response.json()
        log.msg(f'POST to {url} with the following result: {result}')
        return result

    def _parse_command(self, message):
        # TODO(kszucs): make it more sophisticated
        mention = f'@{BOTNAME}'
        if mention in message:
            return message.split(mention)[-1].lower().strip()
        return None

    @defer.inlineCallbacks
    def handle_issue_comment(self, payload, event):
        issue = payload['issue']
        comments_url = issue['comments_url']
        command = self._parse_command(payload['comment']['body'])

        if payload['sender']['login'] == BOTNAME:
            # don't respond to itself
            return [], 'git'
        elif command is None:
            # ursabot is not mentioned, nothing to do
            return [], 'git'
        elif command == 'build':
            if 'pull_request' not in issue:
                message = 'Ursabot only listens to pull request comments!'
                yield self._post(comments_url, {'body': message})
                return [], 'git'
        else:
            message = f'Unknown command "{command}"'
            yield self._post(comments_url, {'body': message})
            return [], 'git'

        try:
            pull_request = yield self._get(issue['pull_request']['url'])
            changes, _ = yield self.handle_pull_request({
                'action': 'synchronize',
                'sender': payload['sender'],
                'repository': payload['repository'],
                'pull_request': pull_request,
                'number': pull_request['number']
            }, event)
        except Exception as e:
            message = "I've failed to start builds for this PR"
            yield self._post(comments_url, {'body': message})
            raise e
        else:
            message = "I've successfully started builds for this PR"
            yield self._post(comments_url, {'body': message})
            return changes, 'git'

    # TODO(kszucs):
    # handle_commit_comment d
    # handle_pull_request_review
    # handle_pull_request_review_comment
