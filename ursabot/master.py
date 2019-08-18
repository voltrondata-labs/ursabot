import copy

from twisted.internet import defer
from zope.interface import implementer
from buildbot import interfaces
from buildbot.master import BuildMaster
from buildbot.util.logger import Logger
from buildbot.process.results import ALL_RESULTS

from .configs import MasterConfig, collect_global_errors
from .utils import ensure_deferred

__all__ = ['TestMaster']


log = Logger()


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
        # deepcopy the whole configuration unless multiple TestMaster cannot
        # be used with the same configuration withing the same process
        config = copy.deepcopy(config)
        with collect_global_errors(and_raise=True):
            self.config = config.as_testing(source)

    def loadConfig(self):
        return self.config


class TestMaster:

    def __init__(self, config, reactor=None, source='TestMaster',
                 log_handler=None, attach_on=tuple()):
        """Lightweight in-process BuildMaster

        Spins up a lightweight BuildMaster in the same process and can trigger
        builders defined in the configuration. The TestMaster only pays
        attention to the `workers`, `builders` and `schedulers` configuration
        keys, so it doesn't configure non-essential services like the
        reporters.
        It is used in the CLI interface to locally reproduce specific builds,
        but it is also suitable for general integration testing of the
        builders.

        Parameters
        ----------
        config: MasterConfig
        reactor: twisted.reactor, default None
        source: str, default `TestMaster`
            Used for highligting the origin or the build properties.
        log_handler: Callable[[unseen_log_lines], None], default lambda _: None
            A callback to handle the logs produced by the builder's buildsteps.
        attach_on: List[Results], default []
            If a build finishes with any of the listed states and it is
            executed withing a DockerLatentWorker then start an interactive
            shell session in the container. Use it with caution, because it
            blocks the event loop.
        """
        assert isinstance(config, MasterConfig)
        assert all(result in ALL_RESULTS for result in attach_on)
        self.config = config
        self.attach_on = set(attach_on)

        loader = EagerLoader(config, source=source)
        if reactor is None:
            from twisted.internet import reactor

        self._source = source
        self._master = BuildMaster('.', reactor=reactor, config_loader=loader)
        self._log_handler = log_handler or (lambda _: None)

        # state variable updated by the event handlers below
        self._buildset = None
        self._buildset_id = None
        self._log_offset = 0

    async def _setup_consumers(self):
        start_consuming = self._master.mq.startConsuming
        self._consumers = [
            await start_consuming(
                callback=self._on_log_creation,
                filter=('logs', None, 'new')
            ),
            await start_consuming(
                callback=self._on_log_append,
                filter=('logs', None, 'append')
            ),
            await start_consuming(
                callback=self._on_build_finished,
                filter=('builds', None, 'finished')
            ),
            await start_consuming(
                callback=self._on_buildset_complete,
                filter=('buildsets', None, 'complete')
            )
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
    async def _on_log_creation(self, key, log):
        self._log_offset = 0

    @ensure_deferred
    async def _on_log_append(self, key, log):
        if log['type'] not in {'t', 's'}:
            # we don't handle html logs on the console
            return

        contents = await self._master.data.get(
            ('logs', log['logid'], 'contents')
        )
        unseen = contents['content'][self._log_offset:]
        self._log_offset += len(unseen)
        self._log_handler(unseen.splitlines())

    @ensure_deferred
    async def _on_build_finished(self, key, build):
        if build['results'] not in self.attach_on:
            return

        for registration in self._master.workers.registrations.values():
            worker = registration.worker
            if worker.workerid == build['workerid']:
                if not hasattr(worker, 'attach_interactive_shell'):
                    log.error(f"{worker} doesn't support interactive shell "
                              f'attachment.')
                else:
                    worker.attach_interactive_shell()

    @ensure_deferred
    async def _on_buildset_complete(self, key, buildset):
        assert buildset['bsid'] == self._buildset_id
        self._buildset.callback(buildset)

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
