from buildbot.test.fake import docker
from buildbot.test.fake import fakemaster
from buildbot.worker import docker as dockerworker
from buildbot.test.unit.test_worker_docker import TestDockerLatentWorker

from ursabot.workers import DockerLatentWorker


class TestDockerLatentWorker(TestDockerLatentWorker):

    def setupWorker(self, *args, **kwargs):
        # licensing copied from the original implementation of
        # TestDockerLatentWorker with a minor modification
        self.patch(dockerworker, 'docker', docker)
        worker = DockerLatentWorker(*args, **kwargs)
        master = fakemaster.make_master(self, wantData=True)
        fakemaster.master = master
        worker.setServiceParent(master)
        self.successResultOf(master.startService())
        self.addCleanup(master.stopService)
        return worker
