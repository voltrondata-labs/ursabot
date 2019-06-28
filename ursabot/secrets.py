# This file is mostly a derivative work of Buildbot.
#
# Buildbot is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os

from twisted.internet import utils
from buildbot.secrets.providers import passwordstore
from buildbot.util.logger import Logger

from .utils import ensure_deferred


log = Logger()


class SecretInPass(passwordstore.SecretInPass):
    """Secret stored in a password store"""

    name = 'SecretInPass'

    def checkConfig(self, passphrase=None, dirname=None):
        self.checkPassIsInPath()
        if dirname:
            self.checkPassDirectoryIsAvailableAndReadable(dirname)

    def reconfigService(self, passphrase=None, dirname=None):
        self._env = os.environ.copy()
        if passphrase:
            self._env['PASSWORD_STORE_GPG_OPTS'] = f'--passphrase {passphrase}'
        if dirname:
            self._env['PASSWORD_STORE_DIR'] = str(dirname)

    @ensure_deferred
    async def get(self, entry):
        """Get the value from pass identified by 'entry'"""
        try:
            output = await utils.getProcessOutput(
                'pass',
                args=[entry],
                env=self._env
            )
        except Exception as e:
            log.error(e)
            return None
        else:
            return output.decode('utf-8', 'ignore').splitlines()[0]
