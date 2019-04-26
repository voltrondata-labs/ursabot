# create an abstraction, e.g. DockerWorkers with an input arguments HOSTS to
# automatically generate DockerLatentWorker's and query them by arch, host,
# and image


from buildbot.plugins import worker, util, schedulers


class WorkerMixin:

    def __init__(self, *args, arch, **kwargs):
        self.arch = arch
        super().__init__(*args, **kwargs)


class DockerLatentWorker(WorkerMixin, worker.DockerLatentWorker):
    pass


class BuilderMixin:

    def __init__(self, *args, workers, **kwargs):
        workernames = [w.name for w in workers]
        super().__init__(*args, workernames=workernames, **kwargs)


class BuilderConfig(BuilderMixin, util.BuilderConfig):
    pass


class SchedulerMixin:

    def __init__(self, *args, builders, **kwargs):
        builder_names = [b.name for b in builders]
        super().__init__(*args, builderNames=builder_names, **kwargs)


class ForceScheduler(SchedulerMixin, schedulers.ForceScheduler):
    pass


class TryScheduler(SchedulerMixin, schedulers.Try_Userpass):
    pass


class AnyBranchScheduler(SchedulerMixin, schedulers.AnyBranchScheduler):
    pass
