import copy
from buildbot import interfaces
from buildbot.plugins import util
from buildbot.plugins import steps as _steps  # ugly

from .steps import (checkout, ls, cmake, compile, test, env,
                    setup, pytest, install, mkdir)
from .steps import ShellCommand, PythonFunction, SetPropertiesFromEnv


class BuildFactory(util.BuildFactory):

    def clone(self):
        return copy.deepcopy(self)

    def add_step(self, step):
        return super().addStep(step)

    def add_steps(self, steps):
        return super().addSteps(steps)

    def prepend_step(self, step):
        self.steps.insert(0, interfaces.IBuildStepFactory(step))


# TODO(kszucs): create popert build factory abstractions for cpp and
#               python builds, e.g. for passing build properties to the build
#               itself instead of using a step for it


cpp = BuildFactory([
    checkout,
    ls,
    env,
    mkdir,
    ls,
    cmake,
    compile,
    test
])

python = BuildFactory([
    checkout,
    env,
    _steps.SetProperties({
        'ARROW_PYTHON': 'ON',
        'ARROW_PLASMA': 'ON'
    }),
    mkdir,
    cmake,
    compile,
    install,
    setup,
    pytest
])

conda_props = SetPropertiesFromEnv({
    'CMAKE_AR': 'AR',
    'CMAKE_RANLIB': 'RANLIB',
    'CMAKE_INSTALL_PREFIX': 'CONDA_PREFIX',
    'ARROW_BUILD_TOOLCHAIN': 'CONDA_PREFIX'
})

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
    _steps.SetProperties({
        'ARROW_PYTHON': 'ON',
        'ARROW_PLASMA': 'ON'
    }),
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
    ShellCommand(command=['pip', 'install', 'pytest', 'flake8', 'mock']),
    # --no-binary buildbot is required because buildbot doesn't bundle its
    # tests to binary wheels, but ursabot's test suite depends on buildbot's
    # so install it from source
    ShellCommand(command=['pip', 'install', '--no-binary', 'buildbot',
                          '-e', '.']),
    ShellCommand(command=['flake8']),
    ShellCommand(command=['pytest', '-v', '-m', 'not docker', 'ursabot']),
    ShellCommand(command=['buildbot', 'checkconfig', '.'])
])

ursabot_docker_build = BuildFactory([
    PythonFunction(lambda: 'trying')
])
