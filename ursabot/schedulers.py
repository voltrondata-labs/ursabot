# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

from buildbot.plugins import util
from buildbot.schedulers.basic import AnyBranchScheduler, SingleBranchScheduler
from buildbot.schedulers.trysched import Try_Userpass
from buildbot.schedulers.forcesched import ForceScheduler

__all__ = [
    'ForceScheduler',
    'TryScheduler',
    'AnyBranchScheduler',
    'SingleBranchScheduler'
]


class SchedulerMixin:

    def __init__(self, *args, builders, **kwargs):
        if callable(builders):
            @util.renderable
            def builder_names(props):
                return [builder.name for builder in builders(props)]
        else:
            builder_names = [b.name for b in builders]

        super().__init__(*args, builderNames=builder_names, **kwargs)


class ForceScheduler(SchedulerMixin, ForceScheduler):

    def __init__(self, *args, project, repository, button_name=None,
                 label=None, **kwargs):
        """Improves the default form of ForceScheduler"""
        codebase = util.CodebaseParameter(
            codebase='',
            label='',
            project=util.FixedParameter(name='project', default=project),
            repository=util.FixedParameter(name='repository',
                                           default=repository),
            branch=util.StringParameter(name='branch',
                                        default='master',
                                        required=True),
            # required, otherwise status push reporter fails with a
            # non-descriptive exception
            revision=util.StringParameter(name='revision', default='HEAD',
                                          required=True)
        )
        kwargs['buttonName'] = button_name or f'Build {project}'
        kwargs['label'] = label or f'Manual {project} build'
        super().__init__(*args, codebases=[codebase], **kwargs)


class TryScheduler(SchedulerMixin, Try_Userpass):
    pass


class AnyBranchScheduler(SchedulerMixin, AnyBranchScheduler):
    pass


class SingleBranchScheduler(SchedulerMixin, SingleBranchScheduler):
    pass
