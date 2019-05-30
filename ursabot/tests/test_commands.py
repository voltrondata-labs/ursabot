import pytest

from ursabot.commands import ursabot_comment_handler


@pytest.mark.parametrize(('command', 'expected_args'), [
    ('crossbow test docker', ['submit', '-c', 'tests.yml', '-g', 'docker']),
    ('crossbow test integration docker',
     ['submit', '-c', 'tests.yml', '-g', 'integration', '-g', 'docker']),
    ('crossbow test docker cpp-python',
     ['submit', '-c', 'tests.yml', '-g', 'docker', '-g', 'cpp-python'])
])
def test_invoking_crossbow(command, expected_args):
    props = ursabot_comment_handler(command)
    expected = {'command': 'crossbow', 'crossbow_args': expected_args}
    assert props == expected


# test failures
