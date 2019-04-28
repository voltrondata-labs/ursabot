from buildbot.plugins import worker


class WorkerMixin:

    def __init__(self, *args, arch, **kwargs):
        self.arch = arch
        super().__init__(*args, **kwargs)


class DockerLatentWorker(WorkerMixin, worker.DockerLatentWorker):
    pass
