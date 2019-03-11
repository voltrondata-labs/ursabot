import copy
from buildbot import interfaces
from buildbot.plugins import util

from .steps import (checkout, ls, mkdir, cmake, compile, test, echo, env,
                    env_old)


class BuildFactory(util.BuildFactory):

    def clone(self):
        return copy.deepcopy(self)

    def add_step(self, step):
        return super().addStep(step)

    def add_steps(self, steps):
        return super().addSteps(steps)

    def prepend_step(self, step):
        self.steps.insert(0, interfaces.IBuildStepFactory(step))


cpp = BuildFactory([
    checkout,
    ls,
    mkdir,
    env_old,
    env,
    cmake,
    compile,
    test
])

echo_factory = BuildFactory()
echo_factory.add_step(checkout)
echo_factory.add_step(ls)
echo_factory.add_step(echo)
