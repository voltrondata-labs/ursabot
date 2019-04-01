# from twisted.python import log

from buildbot.www.hooks.github import GitHubEventHandler


class GithubHook(GitHubEventHandler):

    def handle_blah(self, payload):
        # Do some magic here
        return [], 'git'
