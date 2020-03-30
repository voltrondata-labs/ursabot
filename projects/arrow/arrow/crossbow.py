# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

from buildbot.plugins import util
from ursabot.builders import DockerBuilder
from ursabot.utils import Extend, Filter
from ursabot.steps import GitHub
from .steps import Crossbow


arrow_repository = util.Property(
    'repository',
    default='https://github.com/apache/arrow'
)
crossbow_repository = util.Property(
    'crossbow_repository',
    default='https://github.com/ursa-labs/crossbow'
)
crossbow_prefix = util.Property('crossbow_prefix', 'ursabot')


class CrossbowBuilder(DockerBuilder):
    """Builder to trigger various crossbow tasks

    The crossbow tool is hosted within arrow, so we need to clone both arrow
    and the crossbow repository which serves as a queue for 3rdparty CI
    services like Travis or CircleCI. Then using crossbow's command line
    interface it triggers builds by adding new branches to the crossbow
    repository.
    """
    tags = ['crossbow']
    env = dict(
        GIT_COMMITTER_NAME='ursabot',
        GIT_COMMITTER_EMAIL='ursabot@ci.ursalabs.org'
    )
    steps = [
        GitHub(
            name='Clone Arrow',
            repourl=arrow_repository,
            workdir='arrow',
            mode='full'
        ),
        GitHub(
            name='Clone Crossbow',
            repourl=crossbow_repository,
            workdir='crossbow',
            branch='master',
            mode='full',
            # quite misleasing option, but it prevents checking out the branch
            # set in the sourcestamp by the pull request, which refers to arrow
            alwaysUseLatest=True
        )
    ]
    image_filter = Filter(
        name='crossbow',
        tag='worker'
    )


class CrossbowSubmit(CrossbowBuilder):
    """Submit crossbow jobs

    This builder is driven via buildbot properties, the `crossbow_args`
    property is either set by the github hook which parses the github comments
    like `@ursabot package -g conda` (ror more see commands.py) or by
    explicitly passing by NightlySchedulers.
    """
    steps = Extend([
        Crossbow(
            args=util.FlattenList([
                '--output-file', 'result.yaml',
                '--github-token', util.Secret('kszucs/github_status_token'),
                'submit',
                '--arrow-remote', arrow_repository,
                '--job-prefix', crossbow_prefix,
                util.Property('crossbow_args', [])
            ]),
            workdir='arrow/dev/tasks',
            result_file='result.yaml'
        )
    ])


class CrossbowGithubPage(CrossbowBuilder):
    steps = Extend([
        Crossbow(
            name="Update Crossbow's Github page",
            args=util.FlattenList([
                '--github-token', util.Secret('ursabot/github_token'),
                'github-page',
                'generate',
                '-n', 20,
                '--github-push-token',
                util.Secret('kszucs/github_status_token')
            ]),
            workdir='arrow/dev/tasks'
        )
    ])
