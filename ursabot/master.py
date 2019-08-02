from twisted.internet import defer
from zope.interface import implementer
from buildbot import interfaces
from buildbot.master import BuildMaster

from .configs import MasterConfig, collect_global_errors
from .utils import ensure_deferred

__all__ = ['TestMaster']


@implementer(interfaces.IConfigLoader)
class EagerLoader:

    def __init__(self, config, source='<memory>'):
        """Eagerly loads the master configuration as testing configuration.

        It is required, because Buildbot's BuildMaster implementation does the
        configuration loading in the async startService method, and doesn't
        raise any errors for issues, only logs them and immediately stops the
        twisted reactor (event loop).
        """
        assert isinstance(config, MasterConfig)
        with collect_global_errors(and_raise=True):
            self.config = config.as_testing(source)

    def loadConfig(self):
        return self.config


class TestMaster:

    def __init__(self, config, reactor=None, source=None, logger=None):
        """Construct TestMaster

        Parameters
        ----------
        config: MasterConfig

        """
        assert isinstance(config, MasterConfig)
        self.config = config

        loader = EagerLoader(config, source=source)
        if reactor is None:
            from twisted.internet import reactor

        self._source = source or 'TestMaster'
        self._master = BuildMaster('.', reactor=reactor, config_loader=loader)
        self._log_handler = logger or (lambda _: None)

        # state variable updated by the event handlers below
        self._buildset = None
        self._buildset_id = None
        self._log_offset = 0

    async def _setup_consumers(self):
        start = self._master.mq.startConsuming
        self._consumers = [
            await start(self._on_log_creation, filter=('logs', None, 'new')),
            await start(self._on_log_append, filter=('logs', None, 'append')),
            await start(self._on_buildset_complete,
                        filter=('buildsets', None, 'complete'))
        ]

    async def _stop_consumers(self):
        for consumer in self._consumers:
            consumer.stopConsuming()

    async def __aenter__(self):
        # BuildMaster.startService() doesn't raise, it logs the issues and
        # stops the reactor
        await self._master.startService()
        await self._setup_consumers()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._stop_consumers()
        await self._master.stopService()

    @ensure_deferred
    async def _on_buildset_complete(self, key, buildset):
        assert buildset['bsid'] == self._buildset_id
        self._buildset.callback(buildset)

    @ensure_deferred
    async def _on_log_creation(self, key, log):
        self._log_offset = 0

    @ensure_deferred
    async def _on_log_append(self, key, log):
        contents = await self._master.data.get(
            ('logs', log['logid'], 'contents')
        )
        unseen = contents['content'][self._log_offset:]
        self._log_offset += len(unseen)
        self._log_handler(unseen.splitlines())

    async def build(self, builder_name, sourcestamp, properties=None):
        # the build's outcome is stored in this deferred, set by the
        # _on_buildset_complete event handler
        self._buildset = defer.Deferred()

        if properties is None:
            properties = {}
        else:
            properties = {k: (v, self._source) for k, v in properties.items()}

        updates = self._master.data.updates
        builder_id = await updates.findBuilderId(builder_name)
        self._buildset_id, _ = await updates.addBuildset(
            waited_for=False,
            properties=properties,
            builderids=[builder_id],
            sourcestamps=[sourcestamp]
        )
        return await self._buildset
