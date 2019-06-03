import pytest

from ursabot.commands import CommandError, ursabot


@pytest.mark.parametrize(('command', 'expected_props'), [
    ('build', {'command': 'build'}),
    ('benchmark', {'command': 'benchmark'})
])
def test_ursabot_commands(command, expected_props):
    props = ursabot(command)
    assert props == expected_props


@pytest.mark.parametrize(('command', 'expected_args'), [
    ('crossbow test docker', ['-c', 'tests.yml', '-g', 'docker']),
    ('crossbow test integration docker',
     ['-c', 'tests.yml', '-g', 'integration', '-g', 'docker']),
    ('crossbow test docker cpp-python',
     ['-c', 'tests.yml', '-g', 'docker', '-g', 'cpp-python'])
])
def test_crossbow_commands(command, expected_args):
    props = ursabot(command)
    expected = {'command': 'crossbow', 'crossbow_args': expected_args}
    assert props == expected


@pytest.mark.parametrize(('command', 'expected_msg'), [
    ('buil', 'No such command "buil".'),
    ('bench', 'No such command "bench".'),
    ('crossbow something', 'No such command "something".'),
    ('crossbow test pkgs', 'Invalid value for "[[docker|integration|'
                           'cpp-python]]...": invalid choice: pkgs. '
                           '(choose from docker, integration, cpp-python)')
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
