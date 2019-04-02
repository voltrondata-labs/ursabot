from urllib.parse import urlparse

from twisted.python import log
from twisted.internet import defer

from buildbot.www.hooks.github import GitHubEventHandler
from buildbot.util.httpclientservice import HTTPClientService


BOTNAME = 'ursabot'


class GithubHook(GitHubEventHandler):

    def _get_github_client(self):
        headers = {'User-Agent': 'Buildbot'}
        if self._token:
            headers['Authorization'] = 'token ' + self._token

        return HTTPClientService.getService(
            self.master, self.github_api_endpoint, headers=headers,
            debug=self.debug, verify=self.verify)

    def _parse_command(self, message):
        # TODO(kszucs): make it more sophisticated
        mention = f'@{BOTNAME}'
        if mention in message:
            return message.split(mention)[-1]
        return None

    @defer.inlineCallbacks
    def _answer(self, to_url, message):
        url = urlparse(to_url)
        data = {'body': message}
        log.msg(f'Sending answer "{message}" to {url.path}')

        client = yield self._get_github_client()
        result = yield client.post(url.path, json=data)
        data = yield result.json()
        log.msg(f'Comment is sent with the following result: {data}')

    # TODO(kszucs):
    # handle_commit_comment - there is no comments_url?
    # handle_pull_request_review
    # handle_pull_request_review_comment

    @defer.inlineCallbacks
    def handle_issue_comment(self, payload, event):
        url = payload['issue']['comments_url']
        body = payload['comment']['body']
        sender = payload['sender']['login']

        if sender == BOTNAME:
            # don't respond to itself!
            return [], 'git'

        command = self._parse_command(body)
        if command is None:
            message = 'Wrong command, start with @ursabot!'
        else:
            message = 'Good command!'

        yield self._answer(url, message)

        return [], 'git'
