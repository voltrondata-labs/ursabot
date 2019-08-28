# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import sys
from setuptools import setup


if sys.version_info < (3, 6):
    sys.exit('Python < 3.6 is not supported due to missing asyncio support')


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='ursabot',
    description='Extension for the Buildbot continuous integration tool',
    keywords=['ursabot', 'buildbot', 'ci', 'continuous-integration'],
    long_description=readme(),
    long_description_content_type='text/markdown',
    use_scm_version=True,
    url='http://github.com/ursa-labs/ursabot',
    maintainer='Ursa-Labs team',
    maintainer_email='team@ursalabs.org',
    packages=['ursabot'],
    setup_requires=['setuptools_scm'],
    python_requires='>=3.6',
    install_requires=[
        'buildbot-console-view',
        'buildbot-grid-view',
        'buildbot-waterfall-view',
        'buildbot-worker',
        'buildbot-www',
        'buildbot',
        'click',
        'distro',
        'docker-map',
        'docker',
        'dockerpty',
        'python-dotenv',
        'ruamel.yaml',
        'tabulate',
        'toolz',
        'toposort',
        'treq',
        'twisted[tls]',
        'typeguard'
    ],
    tests_require=['pytest>=3.9', 'mock'],
    entry_points={
        'console_scripts': [
            'ursabot = ursabot.cli:ursabot'
        ]
    },
    zip_safe=False,
)
