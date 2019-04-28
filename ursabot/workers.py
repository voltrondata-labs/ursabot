from buildbot.plugins import worker


# TODO: support specifying parameters to improve isolation, like:
#   cpu_shares, isolation(cgroups), mem_limit and runtime (which will be
#   required for nvidia builds)
# https://docker-py.readthedocs.io/en/stable/api.html
# docker.api.container.ContainerApiMixin.create_host_config


class WorkerMixin:

    def __init__(self, *args, arch, **kwargs):
        self.arch = arch
        super().__init__(*args, **kwargs)


class DockerLatentWorker(WorkerMixin, worker.DockerLatentWorker):

    def renderWorkerProps(self, build):
        # ensure that image is string in case of DockerImage instances
        return build.render((str(self.image), self.dockerfile, self.volumes))
