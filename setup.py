# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import sys
from setuptools import setup


if sys.version_info < (3, 6):
    sys.exit('Python < 3.6 is not supported due to missing asyncio support')


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
        'twisted[tls]'
    ],
    tests_require=['pytest>=3.9', 'mock'],
    entry_points={
        'console_scripts': [
            'ursabot = ursabot.cli:ursabot'
        ]
    },
    zip_safe=False,
)
