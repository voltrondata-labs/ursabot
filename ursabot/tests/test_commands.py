# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

# import pytest
#
# from ursabot.commands import CommandError, ursabot

# TODO(kszucs): write tests, including a plugging-in mechanism for injecting
# commands from projects (like arrow and ursabot)

from copy import copy

import pytest
from ursabot.commands import ursabot


ursabot_copy = copy(ursabot)


@ursabot_copy.command()
def build():
    """Trigger all tests registered for this pull request."""
    # each command must return a dictionary which are set as build properties
    return {'command': 'build'}


@pytest.mark.parametrize(('command', 'expected_props'), [
    ('build', {'command': 'build'}),
])
def test_ursabot_commands(command, expected_props):
    props = ursabot_copy(command)
    assert props == expected_props
