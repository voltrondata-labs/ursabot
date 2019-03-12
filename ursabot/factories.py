import copy
from buildbot import interfaces
from buildbot.plugins import util

from .steps import (checkout, ls, cmake, compile, test, echo, aranlib, env,
                    setup, pytest, install)


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
    env,
    aranlib,
    cmake,
    compile,
    test
])

python = BuildFactory([
    checkout,
    env,
    aranlib,
    cmake,
    compile,
    install,
    ls,
    setup,
    pytest
])

echo_factory = BuildFactory()
echo_factory.add_step(checkout)
echo_factory.add_step(ls)
echo_factory.add_step(echo)
