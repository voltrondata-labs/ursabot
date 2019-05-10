# flake8: noqa  todo removeme
from buildbot.process.results import FAILURE, SUCCESS, EXCEPTION
from buildbot.test.unit import test_reporter_github as original

from ursabot.reporters import (GitHubStatusPush, GitHubReviewPush,
                               GitHubCommentPush)
from ursabot.utils import ensure_deferred


class TestGitHubStatusPush(original.TestGitHubStatusPush):

    def setService(self):
        # test or own implementation
        self.sp = GitHubStatusPush(token='XXYYZZ')
        return self.sp


class TestGitHubStatusPushURL(original.TestGitHubStatusPushURL):
    # project must be in the form <owner>/<project>
    TEST_PROJECT = 'buildbot'
    TEST_REPO = 'https://github.com/buildbot1/buildbot1.git'

    def setService(self):
        # test or own implementation
        self.sp = GitHubStatusPush(token='XXYYZZ')
        return self.sp


class TestGitHubReviewPush(TestGitHubStatusPush):

    def setService(self):
        self.sp = GitHubReviewPush(token='XXYYZZ')
        return self.sp

    @ensure_deferred
    async def test_basic(self):
        build = await self.setupBuildResults(SUCCESS)

        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': '',
                'commit_id': 'd34db33fd43db33f'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'APPROVE',
                'commit_id': 'd34db33fd43db33f'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'REQUEST_CHANGES',
                'commit_id': 'd34db33fd43db33f'
            }
        )
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/pulls/34/reviews',
            json={
                'event': 'REQUEST_CHANGES',
                'commit_id': 'd34db33fd43db33f'
            }
        )

        build['complete'] = False
        self.sp.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = EXCEPTION
        self.sp.buildFinished(('build', 20, 'finished'), build)


class TestGitHubCommentPush(original.TestGitHubCommentPush):

    def setService(self):
        # test or own implementation
        self.sp = GitHubCommentPush(token='XXYYZZ')
        return self.sp

    @ensure_deferred
    async def test_basic(self):
        build = await self.setupBuildResults(SUCCESS)

        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'success'})
        self._http.expect(
            'post',
            '/repos/buildbot/buildbot/issues/34/comments',
            json={'body': 'failure'})

        build['complete'] = False
        self.sp.buildStarted(('build', 20, 'started'), build)
        build['complete'] = True
        self.sp.buildFinished(('build', 20, 'finished'), build)
        build['results'] = FAILURE
        self.sp.buildFinished(('build', 20, 'finished'), build)


# {
#     'buildid': 122,
#     'number': 13,
#     'builderid': 320,
#     'buildrequestid': 534,
#     'workerid': 2,
#     'masterid': 1,
#     'started_at': datetime.datetime(2019, 5, 9, 15, 15, 31, tzinfo=tzutc()),
#     'complete_at': datetime.datetime(2019, 5, 9, 15, 15, 39, 554870, tzinfo=tzutc()),
#     'complete': True,
#     'state_string': 'build successful',
#     'results': 0,
#     'properties': {
#         'reason': ('force build', 'Force Build Form'),
#         'owner': ('', 'Force Build Form'),
#         'scheduler': ('ursabot-force-scheduler', 'Scheduler'),
#         'buildername': ('Ursabot Python 3.7', 'Builder'),
#         'docker_image': ('ursalab/amd64-debian-ursabot:worker', 'Builder'),
#         'workername': ('local1-docker', 'Worker'),
#         'buildnumber': (13, 'Build'),
#         'branch': ('refs/pull/66/merge', 'Build'),
#         'revision': ('6fc264c95b8f1ff2fe8f33c824818f7dc1e4dcdf', 'Build'),
#         'repository': ('https://github.com/ursa-labs/ursabot', 'Build'),
#         'codebase': ('', 'Build'),
#         'project': ('ursa-labs/ursabot', 'Build'),
#         'owners': ([''], 'Build'),
#         'builddir': ('/buildbot/Ursabot_Python_3_7', 'Worker')
#     },
#     'buildrequest': {
#         'buildrequestid': 534,
#         'buildsetid': 84,
#         'builderid': 320,
#         'priority': 0,
#         'claimed': True,
#         'claimed_at': datetime.datetime(2019, 5, 9, 15, 15, 31, tzinfo=tzutc()),
#         'claimed_by_masterid': 1,
#         'complete': False,
#         'results': -1,
#         'submitted_at': datetime.datetime(2019, 5, 9, 15, 15, 31, tzinfo=tzutc()),
#         'complete_at': None,
#         'waited_for': False,
#         'properties': None
#     },
#     'buildset': {
#         'external_idstring': None,
#         'reason': 'rebuild',
#         'submitted_at': 1557414931,
#         'complete': False,
#         'complete_at': None,
#         'results': -1,
#         'bsid': 84,
#         'sourcestamps': [
#             {
#                 'ssid': 42,
#                 'branch': 'refs/pull/66/merge',
#                 'revision': '6fc264c95b8f1ff2fe8f33c824818f7dc1e4dcdf',
#                 'project': 'ursa-labs/ursabot',
#                 'repository': 'https://github.com/ursa-labs/ursabot',
#                 'codebase': '',
#                 'created_at': datetime.datetime(2019, 5, 9, 15, 10, 31, 521736, tzinfo=tzutc()),
#                 'patch': None
#             }
#         ],
#         'parent_buildid': None,
#         'parent_relationship': None
#     },
#     'builder': {
#         'builderid': 320,
#         'name': 'Ursabot Python 3.7',
#         'masterids': [1],
#         'description': None,
#         'tags': ['ursabot', 'amd64', 'debian']
#     },
#     'url': 'http://localhost:8100/#builders/320/builds/13',
#     'steps': [
#         {
#             'stepid': 238,
#             'number': 0,
#             'name': 'worker_preparation',
#             'buildid': 122,
#             'started_at': datetime.datetime(2019, 5, 9, 15, 15, 31, tzinfo=tzutc()),
#             'complete': True,
#             'complete_at': datetime.datetime(2019, 5, 9, 15, 15, 34, 893406, tzinfo=tzutc()),
#             'state_string': 'worker ready',
#             'results': 0,
#             'urls': [],
#             'hidden': False,
#             'logs': []
#         },
#         {
#             'stepid': 239,
#             'number': 1,
#             'name': 'Shell',
#             'buildid': 122,
#             'started_at': datetime.datetime(2019, 5, 9, 15, 15, 34, tzinfo=tzutc()),
#             'complete': True,
#             'complete_at': datetime.datetime(2019, 5, 9, 15, 15, 37, 737799, tzinfo=tzutc()),
#             'state_string': ''apt-get update ...'',
#             'results': 0,
#             'urls': [],
#             'hidden': False,
#             'logs': [
#                 {
#                     'logid': 298,
#                     'name': 'stdio',
#                     'slug': 'stdio',
#                     'stepid': 239,
#                     'complete': True,
#                     'num_lines': 29,
#                     'type': 's',
#                     'content': {
#                         'logid': 298,
#                         'firstline': 0,
#                         'content': 'hapt-get update -y\nh in dir /buildbot/Ursabot_Python_3_7/build (timeout 1200 secs)\nh watching logfiles {}\nh argv: [b'apt-ge
# t', b'update', b'-y']\nh environment:\nh  BUILDMASTER=kszucs-mbp.local\nh  BUILDMASTER_PORT=9989\nh  GPG_KEY=0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D\nh  HOME=/root\nh  HOSTNAME=linuxkit-025000000001\nh  LANG=C.UTF-8\nh  PATH=/usr/local/b
# in:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nh  PWD=/buildbot/Ursabot_Python_3_7/build\nh  PYTHON_PIP_VERSION=19.1\nh  PYTHON_VERSION=3.7.3\nh  WORKERNAME=local1-docker\nh using PTY: False\noGet:1 http://security.debia
# n.org/debian-security stretch/updates InRelease [94.3 kB]\noIgn:2 http://deb.debian.org/debian stretch InRelease\noGet:3 http://deb.debian.org/debian stretch-updates InRelease [91.0 kB]\noGet:4 http://deb.debian.org/debian stretch Release
#  [118 kB]\noGet:5 http://deb.debian.org/debian stretch Release.gpg [2434 B]\noGet:6 http://security.debian.org/debian-security stretch/updates/main amd64 Packages [488 kB]\noGet:7 http://deb.debian.org/debian stretch-updates/main amd64 Pa
# ckages [31.7 kB]\noGet:8 http://deb.debian.org/debian stretch/main amd64 Packages [7082 kB]\noFetched 7907 kB in 2s (3924 kB/s)\noReading package lists...\nhprogram finished with exit code 0\nhelapsedTime=2.619199\n'
#                     }
#                 }
#             ]
#         },
#         {
#             'stepid': 240,
#             'number': 2,
#             'name': 'Shell_1',
#             'buildid': 122,
#             'started_at': datetime.datetime(2019, 5, 9, 15, 15, 37, tzinfo=tzutc()),
#             'complete': True,
#             'complete_at': datetime.datetime(2019, 5, 9, 15, 15, 39, 4396, tzinfo=tzutc()),
#             'state_string': ''apt-get install ...'',
#             'results': 0,
#             'urls': [],
#             'hidden': False,
#             'logs': [
#                 {
#                     'logid': 299,
#                     'name': 'stdio',
#                     'slug': 'stdio',
#                     'stepid': 240,
#                     'complete': True,
#                     'num_lines': 24,
#                     'type': 's',
#                     'content': {
#                         'logid': 299,
#                         'firstline': 0,
#                         'content': 'hapt-get install -y curl\nh in dir /buildbot/Ursabot_Python_3_7/build (timeout 1200 secs)\nh watching logfiles {}\nh argv: [b'apt-get', b'install', b'-y', b'curl']\nh environment:\nh  BUILDMASTER=kszucs-mbp.local\nh  BUILDMASTER_PORT=99
# 89\nh  GPG_KEY=0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D\nh  HOME=/root\nh  HOSTNAME=linuxkit-025000000001\nh  LANG=C.UTF-8\nh  PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nh  PWD=/buildbot/Ursabot_Pyth
# on_3_7/build\nh  PYTHON_PIP_VERSION=19.1\nh  PYTHON_VERSION=3.7.3\nh  WORKERNAME=local1-docker\nh using PTY: False\noReading package lists...\noBuilding dependency tree...\noReading state information...\nocurl is already the newest versio
# n (7.52.1-5+deb9u9).\no0 upgraded, 0 newly installed, 0 to remove and 29 not upgraded.\nhprogram finished with exit code 0\nhelapsedTime=1.107848\n'
#                     }
#                 }
#             ]
#         },
#         {
#             'stepid': 241,
#             'number': 3,
#             'name': 'Archery',
#             'buildid': 122,
#             'started_at': datetime.datetime(2019, 5, 9, 15, 15, 39, tzinfo=tzutc()),
#             'complete': True,
#             'complete_at': datetime.datetime(2019, 5, 9, 15, 15, 39, 494241, tzinfo=tzutc()),
#             'state_string': ''curl https://gist.githubusercontent.com/kszucs/ac986d0d3439aebfcc4cd695ca39ce39/raw/e476d5e6b1f916a83187d03dc6c731f4078c6979/gistfile1.txt ...'',
#             'results': 0,
#             'urls': [],
#             'hidden': False,
#             'logs': [
#                 {
#                     'logid': 300,
#                     'name': 'stdio',
#                     'slug': 'stdio',
#                     'stepid': 241,
#                     'complete': True,
#                     'num_lines': 25,
#                     'type': 's',
#                     'content': {
#                         'logid': 300,
#                         'firstline': 0,
#                         'content': 'hcurl https://gist.githubusercontent.com/kszucs/ac986d0d3439aebfcc4cd695ca39ce39/raw/e476d5e6b1f916a83187d03dc6c731f4078c6979/gistfile1.txt --output diff.json\nh in dir /buildbot/
# Ursabot_Python_3_7/build (timeout 1200 secs)\nh watching logfiles {}\nh argv: [b'curl', b'https://gist.githubusercontent.com/kszucs/ac986d0d3439aebfcc4cd695ca39ce39/raw/e476d5e6b1f916a83187d03dc6c731f4078c6979/gistfile1.txt', b'--output',
#  b'diff.json']\nh environment:\nh  BUILDMASTER=kszucs-mbp.local\nh  BUILDMASTER_PORT=9989\nh  GPG_KEY=0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D\nh  HOME=/root\nh  HOSTNAME=linuxkit-025000000001\nh  LANG=C.UTF-8\nh  LC_ALL=C.UTF-8\nh  PATH=
# /usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nh  PWD=/buildbot/Ursabot_Python_3_7/build\nh  PYTHON_PIP_VERSION=19.1\nh  PYTHON_VERSION=3.7.3\nh  WORKERNAME=local1-docker\nh using PTY: False\ne  % Total    %
# Received % Xferd  Average Speed   Time    Time     Time  Current\ne                                 Dload  Upload   Total   Spent    Left  Speed\ne\ne  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0\ne100   9
# 91  100   991    0     0   4499      0 --:--:-- --:--:-- --:--:--  4525\nhprogram finished with exit code 0\nhelapsedTime=0.258428\n'
#                     }
#                 },
#                 {
#                     'logid': 301,
#                     'name': 'result',
#                     'slug': 'result',
#                     'stepid': 241,
#                     'complete': True,
#                     'num_lines': 4,
#                     'type': 't',
#                     'content': {
#                         'logid': 301,
#                         'firstline': 0,
#                         'content': '{'benchmark':'RegressionSumKernel/32768/50','change':-0.001550846227215492,'regression':false,'baseline':19241207435.428757,'contender':19211367281.47045,'unit':'bytes_per_
# second','less_is_better':false,'suite':'arrow-compute-aggregate-benchmark'}\n{'benchmark':'RegressionSumKernel/32768/1','change':-0.0020681767923465765,'regression':false,'baseline':24823170673.777943,'contender':24771831968.277977,'unit'
# :'bytes_per_second','less_is_better':false,'suite':'arrow-compute-aggregate-benchmark'}\n{'benchmark':'RegressionSumKernel/32768/10','change':0.0033323376378746905,'regression':false,'baseline':21902707565.968014,'contender':21975694782.7
# 6145,'unit':'bytes_per_second','less_is_better':false,'suite':'arrow-compute-aggregate-benchmark'}\n{'benchmark':'RegressionSumKernel/32768/0','change':0.004918126090954414,'regression':false,'baseline':27685006611.446762,'contender':2782
# 1164964.790764,'unit':'bytes_per_second','less_is_better':false,'suite':'arrow-compute-aggregate-benchmark'}\n'
#                     }
#                 }
#             ]
#         }
#     ]
# }
