from buildbot.plugins import schedulers, util


class SchedulerMixin:

    def __init__(self, *args, builders, **kwargs):
        builder_names = [b.name for b in builders]
        super().__init__(*args, builderNames=builder_names, **kwargs)


class GithubSchedulerMixin:
    """ Improves the default form of ForceScheduler. """

    def __init__(self, *args, project, **kwargs):
        codebase = util.CodebaseParameter(
            codebase='',
            label='',
            branch=util.StringParameter(name='branch',
                                        default='master',
                                        required=True),
            commit=util.StringParameter(name='commit', required=True),
            project=util.FixedParameter(name='project', default=project),
            repository=util.FixedParameter(name='repository', default=project),
        )
        super().__init__(*args, codebases=[codebase], **kwargs)


class ForceScheduler(SchedulerMixin, GithubSchedulerMixin,
                     schedulers.ForceScheduler):
    pass


class TryScheduler(SchedulerMixin, schedulers.Try_Userpass):
    pass


class AnyBranchScheduler(SchedulerMixin, schedulers.AnyBranchScheduler):
    pass
