#!/usr/bin/env python

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
        'codenamize',
        'docker',
        'docker-map',
        'ruamel.yaml',
        'tabulate',
        'toml',
        'toolz',
        'toposort',
        'treq',
    ],
    tests_require=['pytest>=3.9', 'mock'],
    entry_points="""
        [console_scripts]
        ursabot=ursabot.cli:ursabot
    """,
    zip_safe=False,
)
