import copy
from buildbot import interfaces
from buildbot.plugins import util

from .steps import (checkout, ls, cmake, compile, test, echo, env_old, aranlib,
                    conda_cmake)


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
    env_old,
    cmake,
    compile,
    test
])

conda_cpp = BuildFactory([
    checkout,
    env_old,
    aranlib,
    conda_cmake,
    compile,
    test
])

echo_factory = BuildFactory()
echo_factory.add_step(checkout)
echo_factory.add_step(ls)
echo_factory.add_step(echo)
