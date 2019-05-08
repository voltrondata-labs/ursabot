#!/usr/bin/env python

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
