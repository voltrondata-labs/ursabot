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
