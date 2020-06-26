# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import pytest
from ursabot.commands import CommandError

from ..commands import ursabot


@pytest.mark.parametrize(('command', 'expected_props'), [
    ('build', {'command': 'build'}),
    ('benchmark', {'command': 'benchmark',
                   'benchmark_options': ['--repetitions=1']})
])
def test_ursabot_commands(command, expected_props):
    props = ursabot(command)
    assert props == expected_props


@pytest.mark.parametrize(('command', 'expected_args'), [
    ('crossbow submit -g docker', ['-c', 'tasks.yml', '-g', 'docker']),
    ('crossbow submit -g integration -g docker',
     ['-c', 'tasks.yml', '-g', 'integration', '-g', 'docker']),
    ('crossbow submit -g docker -g cpp-python',
     ['-c', 'tasks.yml', '-g', 'docker', '-g', 'cpp-python']),
    ('crossbow submit wheel-osx-cp27m ubuntu-xenial',
     ['-c', 'tasks.yml', 'wheel-osx-cp27m', 'ubuntu-xenial']),
    ('crossbow submit -g wheel -g conda',
     ['-c', 'tasks.yml', '-g', 'wheel', '-g', 'conda']),
    ('crossbow submit -g wheel -g conda wheel-win-cp37m wheel-osx-cp27m',
     ['-c', 'tasks.yml', '-g', 'wheel', '-g', 'conda', 'wheel-win-cp37m',
      'wheel-osx-cp27m']),
    ('crossbow submit docker-python-3.6-nopandas docker-python-3.7-nopandas',
     ['-c', 'tasks.yml', 'docker-python-3.6-nopandas',
      'docker-python-3.7-nopandas']),
    ('crossbow submit -g cpp-python docker-python-3.6-nopandas',
     ['-c', 'tasks.yml', '-g', 'cpp-python', 'docker-python-3.6-nopandas'])
])
def test_crossbow_commands(command, expected_args):
    props = ursabot(command)
    expected = {
        'command': 'crossbow',
        'crossbow_repo': 'ursa-labs/crossbow',
        'crossbow_repository': 'https://github.com/ursa-labs/crossbow',
        'crossbow_args': expected_args
    }
    assert props == expected


@pytest.mark.parametrize(('command', 'expected_repo'), [
    ('crossbow submit -g docker', 'ursa-labs/crossbow'),
    ('crossbow -r ursa-labs/crossbow submit -g docker', 'ursa-labs/crossbow'),
    ('crossbow -r kszucs/crossbow submit -g docker', 'kszucs/crossbow'),
])
def test_crossbow_repo(command, expected_repo):
    props = ursabot(command)
    expected = {
        'command': 'crossbow',
        'crossbow_repo': expected_repo,
        'crossbow_repository': f'https://github.com/{expected_repo}',
        'crossbow_args': ['-c', 'tasks.yml', '-g', 'docker']
    }
    assert props == expected


def test_benchmark_options():
    command = (
        'benchmark --suite-filter=arrow-compute-vector-sort-benchmark '
        '--cc=clang-8 --cxx=clang++-8 --cxx-flags=anything'
    )
    props = ursabot(command)
    expected = {
        'command': 'benchmark',
        'benchmark_options': [
            '--suite-filter=arrow-compute-vector-sort-benchmark',
            '--cc=clang-8',
            '--cxx=clang++-8',
            '--cxx-flags=anything',
            '--repetitions=1'
        ]
    }
    assert props == expected


@pytest.mark.parametrize(('command', 'expected_msg'), [
    ('buil', 'No such command "buil".'),
    ('bench', 'No such command "bench".'),
    ('crossbow something', 'No such command "something".'),
])
def test_wrong_commands(command, expected_msg):
    with pytest.raises(CommandError) as excinfo:
        ursabot(command)
    assert excinfo.value.message == expected_msg


@pytest.mark.parametrize('command', [
    '',
    '--help',
])
def test_ursabot_help(command):
    with pytest.raises(CommandError) as excinfo:
        ursabot(command)
    prefix = 'Usage: @ursabot [OPTIONS] COMMAND [ARGS]...'
    assert excinfo.value.message.startswith(prefix)


@pytest.mark.parametrize('command', [
    'crossbow',
    'crossbow --help',
])
def test_ursabot_crossbow_help(command):
    with pytest.raises(CommandError) as excinfo:
        ursabot(command)
    prefix = 'Usage: @ursabot crossbow [OPTIONS] COMMAND [ARGS]...'
    assert excinfo.value.message.startswith(prefix)
