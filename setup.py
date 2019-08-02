# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import sys
from setuptools import setup


if sys.version_info < (3, 6):
    sys.exit('Python < 3.6 is not supported due to missing asyncio support')


def plugins(module, symbols):
    return ['{1} = {0}:{1}'.format(module, symbol) for symbol in symbols]


# TODO(kszucs): add package data, change maintainer
setup(
    name='ursabot',
    description='Ursa-labs continuous integration tool',
    use_scm_version=True,
    url='http://github.com/ursa-labs/ursabot',
    maintainer='Krisztian Szucs',
    maintainer_email='szucs.krisztian@gmail.com',
    packages=['ursabot'],
    setup_requires=['setuptools_scm'],
    install_requires=[
        'buildbot-console-view',
        'buildbot-grid-view',
        'buildbot-waterfall-view',
        'buildbot-www',
        'buildbot',
        'click',
        'codenamize',
        'docker-map',
        'docker',
        'python-dotenv',
        'ruamel.yaml',
        'tabulate',
        'toolz',
        'toposort',
        'treq',
        'twisted[tls]'
    ],
    tests_require=['pytest>=3.9', 'mock'],
    entry_points={
        'console_scripts': [
            'ursabot = ursabot.cli:ursabot'
        ],
        'buildbot.changes': plugins(module='ursabot.changes', symbols=[
            'ChangeFilter',
            'GitPoller',
            'GitHubPullrequestPoller'
        ]),
        'buildbot.steps': plugins(module='ursabot.steps', symbols=[
            'Mkdir',
            'GitHub',
            'Cargo',
            'CMake',
            'CTest',
            'Env',
            'Go',
            'Make',
            'Maven',
            'Ninja',
            'Npm',
            'Pip',
            'PyTest',
            'R',
            'ResultLogMixin',
            'SetPropertiesFromEnv',
            'SetPropertyFromCommand',
            'SetupPy',
            'ShellCommand',
        ]),
        'buildbot.schedulers': plugins(module='ursabot.schedulers', symbols=[
            'ForceScheduler',
            'TryScheduler',
            'AnyBranchScheduler',
            'SingleBranchScheduler',
        ]),
        'buildbot.worker': plugins(module='ursabot.worker', symbols=[
            'DockerLatentWorker',
        ]),
        'buildbot.webhooks': plugins(module='ursabot.hooks', symbols=[
            'GithubHoook',
            'UrsabotHook',
        ]),
        'buildbot.secrets': plugins(module='ursabot.secrets', symbols=[
            'SecretInPass',
        ]),
        'buildbot.reporters': (
            plugins(module='ursabot.reporters', symbols=[
                'HttpStatusPush',
                'GitHubReporter',
                'GitHubStatusPush',
                'GitHubReviewPush',
                'GitHubCommentPush',
                'ZulipStatusPush',
            ]) +
            plugins(module='ursabot.formatters', symbols=[
                'Formatter',
                'MarkdownFormatter',
            ])
        ),
        'buildbot.util': (
            plugins(module='ursabot.configs', symbols=[
                'Config',
                'MasterConfig',
                'ProjectConfig',
                'InMemoryLoader',
                'FileLoader',
                'collect_global_errors',
            ]) +
            plugins(module='ursabot.builders', symbols=[
                'BuildFactory',
                'Builder',
                'DockerBuilder',
            ]) +
            plugins(module='ursabot.docker', symbols=[
                'DockerFile',
                'DockerImage',
                'ImageCollection',
                'DockerBuilder',
                'worker_image_for',
                'worker_images_for',
                'ADD',
                'COPY',
                'RUN',
                'ENV',
                'WORKDIR',
                'USER',
                'CMD',
                'SHELL',
                'ENTRYPOINT',
                'symlink',
                'apt',
                'apk',
                'pip',
                'conda',
            ]) +
            plugins(module='ursabot.utils', symbols=[
                'GithubClientService',
                'Collection',
                'Filter',
                'ensure_deferred',
                'read_dependency_list',
                'startswith',
                'any_of',
                'has',
            ])
        )
    },
    zip_safe=False,
)
