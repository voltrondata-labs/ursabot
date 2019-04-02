import copy
from buildbot import interfaces
from buildbot.plugins import util
from buildbot.plugins import steps as _steps  # ugly

from .steps import (checkout, ls, cmake, compile, test, env, cpp_props,
                    setup, pytest, install, mkdir, conda_props, python_props)
from .steps import ShellCommand


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
    mkdir,
    ls,
    cpp_props,
    cmake,
    compile,
    test
])

python = BuildFactory([
    checkout,
    env,
    cpp_props,
    python_props,
    mkdir,
    cmake,
    compile,
    install,
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

# TODO(kszucs): subclass buildfactory to explicitly pass properties, like:
# ARROW_PYTHON=ON

python_conda = BuildFactory([
    checkout,
    env,
    conda_props,
    python_props,
    mkdir,
    cmake,
    compile,
    install,
    setup,
    pytest
])

ursabot_test = BuildFactory([
    _steps.Git(name='Clone Ursabot',
               repourl='https://github.com/ursa-labs/ursabot',
               mode='full'),
    ShellCommand(command=['ls', '-lah']),
    ShellCommand(command=['pip', 'install', 'pytest', 'flake8']),
    ShellCommand(command=['pip', 'install', '-e', '.']),
    ShellCommand(command=['flake8']),
    ShellCommand(command=['pytest', '-v', '-m', '"not docker"', 'ursabot']),
    ShellCommand(command=['buildbot', 'checkconfig', '.'])
])
