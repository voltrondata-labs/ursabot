from buildbot.plugins import worker


class WorkerMixin:

    def __init__(self, *args, arch, **kwargs):
        self.arch = arch
        super().__init__(*args, **kwargs)


class DockerLatentWorker(WorkerMixin, worker.DockerLatentWorker):

    def renderWorkerProps(self, build):
        # ensure that image is string in case of DockerImage instances
        return build.render((str(self.image), self.dockerfile, self.volumes))
