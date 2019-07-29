# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

# import pytest
#
# from ursabot.commands import CommandError, ursabot

import pytest
from ursabot.commands import group


@group()
def custom():
    pass


@custom.command()
def build():
    """Trigger all tests registered for this pull request."""
    # each command must return a dictionary which are set as build properties
    return {'command': 'build'}


@pytest.mark.parametrize(('command', 'expected_props'), [
    ('build', {'command': 'build'}),
])
def test_custom_commands(command, expected_props):
    props = custom(command)
    assert props == expected_props
