from urllib.parse import urlparse

from twisted.python import log
from twisted.internet import defer

from buildbot.www.hooks.github import GitHubEventHandler
from buildbot.util.httpclientservice import HTTPClientService


BOTNAME = 'ursabot'


# rename it to listener
class GithubHook(GitHubEventHandler):

    def _get_github_client(self):
        headers = {'User-Agent': 'Buildbot'}
        if self._token:
            headers['Authorization'] = 'token ' + self._token

        return HTTPClientService.getService(
            self.master, self.github_api_endpoint, headers=headers,
            debug=self.debug, verify=self.verify)

    @defer.inlineCallbacks
    def handle_issue_comment(self, payload, event):
        user = payload['user']['login']
        body = payload['comment']['body']

        if user == BOTNAME:
            # don't respond to itself
            return [], 'git'

        if body.startswith(f'@{BOTNAME} '):
            response = 'Good command!'
        else:
            response = 'Wrong command, start with @ursabot!'

        url = urlparse(payload['issue']['comments_url'])
        data = {'body': response}
        log.msg(f'Sending comment {response} to {url}')

        client = yield self._get_github_client()
        result = yield client.post(url.path, json=data)
        data = yield result.json()
        log.msg(f'Comment sent with the following result: {data}')

        return [], 'git'
