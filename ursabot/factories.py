import copy
from buildbot import interfaces
from buildbot.plugins import util

from .steps import (checkout, ls, cmake, compile, test, aranlib, env,
                    setup, pytest, install, mkdir, conda_props)


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
    env,
    aranlib,
    mkdir,
    ls,
    cmake,
    compile,
    test
])

python = BuildFactory([
    checkout,
    ls,
    env,
    aranlib,
    mkdir,
    ls,
    cmake,
    compile,
    install,
    ls,
    setup,
    pytest
])

cpp_conda = BuildFactory([
    checkout,
    env,
    conda_props,
    mkdir,
    cmake,
    compile,
    test
])

python_conda = BuildFactory([
    checkout,
    env,
    conda_props,
    mkdir,
    cmake,
    compile,
    install,
    setup,
    pytest
])
