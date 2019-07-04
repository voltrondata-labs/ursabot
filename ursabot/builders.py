# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import copy
import toolz
import itertools
import warnings
from collections import defaultdict

from buildbot import interfaces
from buildbot.plugins import util
from codenamize import codenamize

from .docker import DockerImage, images
from .workers import DockerLatentWorker
from .steps import (ShellCommand, SetPropertiesFromEnv,
                    Ninja, SetupPy, CTest, CMake, PyTest, Mkdir, Pip, GitHub,
                    Archery, Crossbow, Maven)
from .utils import Collection, startswith, slugify


class BuildFactory(util.BuildFactory):

    def clone(self):
        return copy.deepcopy(self)

    def add_step(self, step):
        return super().addStep(step)

    def add_steps(self, steps):
        return super().addSteps(steps)

    def prepend_step(self, step):
        self.steps.insert(0, interfaces.IBuildStepFactory(step))


class Builder(util.BuilderConfig):

    # used for generating unique default names
    _ids = defaultdict(itertools.count)
    # merged with env argument
    env = None
    # concatenated to tags constructor argument
    tags = tuple()
    # default for steps argument so it gets overwritten if steps is passed
    steps = tuple()
    # prefix for name argument
    name_prefix = ''
    # merged with properties argument
    properties = None
    # merged with default_properties argument
    default_properties = None

    def __init__(self, name=None, steps=None, factory=None, workers=None,
                 tags=None, properties=None, default_properties=None, env=None,
                 **kwargs):
        if isinstance(steps, (list, tuple)):
            # replace the class' steps
            steps = steps
        elif steps is None:
            steps = self.steps
        else:
            raise TypeError('Steps must be a list')

        if isinstance(tags, (list, tuple)):
            # append to the class' tag list
            tags = filter(None, toolz.concat([self.tags, tags]))
            tags = list(toolz.unique(tags))
        elif tags is not None:
            raise TypeError('Tags must be a list')

        name = name or self._generate_name()
        if self.name_prefix:
            name = f'{self.name_prefix} {name}'
        factory = factory or BuildFactory(steps)
        env = toolz.merge(self.env or {}, env or {})
        properties = toolz.merge(self.properties or {}, properties or {})
        default_properties = toolz.merge(self.default_properties or {},
                                         default_properties or {})

        workernames = None if workers is None else [w.name for w in workers]

        super().__init__(name=name, tags=tags, properties=properties,
                         defaultProperties=default_properties, env=env,
                         workernames=workernames, factory=factory, **kwargs)

    @classmethod
    def _generate_name(cls, prefix=None, slug=True, ids=True, codename=None):
        name = prefix or cls.__name__
        if slug:
            name = slugify(name)
        if ids:
            name += '#{}'.format(next(cls._ids[name]))
        if codename is not None:
            # generates codename like: pushy-idea
            name += ' ({})'.format(codenamize(codename, max_item_chars=5))
        return name

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}'>"


class DockerBuilder(Builder):

    images = tuple()
    hostconfig = None

    def __init__(self, name=None, image=None, properties=None, tags=None,
                 hostconfig=None, **kwargs):
        if not isinstance(image, DockerImage):
            raise ValueError('Image must be an instance of DockerImage')

        name = image.title
        tags = tags or [image.name]
        tags += list(image.platform)
        properties = properties or {}
        properties['docker_image'] = str(image)
        properties['docker_hostconfig'] = toolz.merge(self.hostconfig or {},
                                                      hostconfig or {})
        super().__init__(name=name, properties=properties, tags=tags, **kwargs)

    @classmethod
    def builders_for(cls, workers, images=tuple(), **kwargs):
        """Instantiates builders based on the available workers

        The workers and images are matched based on their architecture.

        Parameters
        ----------
        workers : List[DockerLatentWorker]
            Worker instances the builders may run on.
        images : List[DockerImage], default []
            Docker images the builder's steps may run in.
            Pass None to use class' images property.

        Returns
        -------
        docker_builder : List[DockerBuilder]
            Builder instances.
        """
        assert all(isinstance(i, DockerImage) for i in images)
        assert all(isinstance(w, DockerLatentWorker) for w in workers)

        images = images or cls.images
        workers_by_arch = workers.groupby('arch')

        builders = Collection()
        for image in images:
            if image.arch in workers_by_arch:
                workers = workers_by_arch[image.arch]
                builder = cls(image=image, workers=workers, **kwargs)
                builders.append(builder)
            else:
                warnings.warn(
                    f'{cls.__name__}: there are no docker workers available '
                    f'for architecture `{image.arch}`, omitting image '
                    f'`{image}`'
                )

        return builders


# prefer GitHub over Git step
checkout_arrow = GitHub(
    name='Clone Arrow',
    repourl=util.Property('repository'),
    workdir='.',
    submodules=True,
    mode='full'
)

# explicitly define build definitions, exported via cmake -LAH
definitions = {
    # CMake flags
    'CMAKE_BUILD_TYPE': 'debug',
    'CMAKE_INSTALL_PREFIX': None,
    'CMAKE_INSTALL_LIBDIR': None,
    'CMAKE_CXX_FLAGS': None,
    'CMAKE_AR': None,
    'CMAKE_RANLIB': None,
    'PYTHON_EXECUTABLE': None,
    # Build Arrow with Altivec
    'ARROW_ALTIVEC': 'ON',
    # Rely on boost shared libraries where relevant
    'ARROW_BOOST_USE_SHARED': 'ON',
    # Build the Arrow micro benchmarks
    'ARROW_BUILD_BENCHMARKS': 'OFF',
    # Build the Arrow examples
    'ARROW_BUILD_EXAMPLES': 'OFF',
    # Build shared libraries
    'ARROW_BUILD_SHARED': 'ON',
    # Build static libraries
    'ARROW_BUILD_STATIC': 'ON',
    # Build the Arrow googletest unit tests
    'ARROW_BUILD_TESTS': 'ON',
    # Build Arrow commandline utilities
    'ARROW_BUILD_UTILITIES': 'ON',
    # Build the Arrow Compute Modules
    'ARROW_COMPUTE': 'ON',
    # Build the Arrow CUDA extensions (requires CUDA toolkit)
    'ARROW_CUDA': 'OFF',
    # Compiler flags to append when compiling Arrow
    'ARROW_CXXFLAGS': '',
    # Compile with extra error context (line numbers, code)
    'ARROW_EXTRA_ERROR_CONTEXT': 'ON',
    # Build the Arrow Flight RPC System (requires GRPC, Protocol Buffers)
    'ARROW_FLIGHT': 'OFF',
    # Build Arrow Fuzzing executables
    # 'ARROW_FUZZING': 'OFF',
    # Build the Gandiva libraries
    'ARROW_GANDIVA': 'OFF',
    # Build the Gandiva JNI wrappers
    'ARROW_GANDIVA_JAVA': 'OFF',
    # Compiler flags to append when pre-compiling Gandiva operations
    # 'ARROW_GANDIVA_PC_CXX_FLAGS': '',
    # Include -static-libstdc++ -static-libgcc when linking with Gandiva
    # static libraries
    # 'ARROW_GANDIVA_STATIC_LIBSTDCPP': 'OFF',
    # Build with C++ code coverage enabled
    # 'ARROW_GENERATE_COVERAGE': 'OFF',
    # Rely on GFlags shared libraries where relevant
    # 'ARROW_GFLAGS_USE_SHARED': 'ON',
    # Pass -ggdb flag to debug builds
    # 'ARROW_GGDB_DEBUG': 'ON',
    # Build the Arrow HDFS bridge
    'ARROW_HDFS': 'OFF',
    # Build the HiveServer2 client and Arrow adapter
    # 'ARROW_HIVESERVER2': 'OFF',
    # Build Arrow libraries with install_name set to @rpath
    # 'ARROW_INSTALL_NAME_RPATH': 'ON',
    # Build the Arrow IPC extensions
    'ARROW_IPC': 'ON',
    # Build the Arrow jemalloc-based allocator
    'ARROW_JEMALLOC': 'ON',
    # Exclude deprecated APIs from build
    # 'ARROW_NO_DEPRECATED_API': 'OFF',
    # Only define the lint and check-format targets
    # 'ARROW_ONLY_LINT': 'OFF',
    # If enabled install ONLY targets that have already been built.
    # Please be advised that if this is enabled 'install' will fail silently
    # on components that have not been built.
    # 'ARROW_OPTIONAL_INSTALL': 'OFF',
    # Build the Arrow ORC adapter
    'ARROW_ORC': 'OFF',
    # Build the Parquet libraries
    'ARROW_PARQUET': 'OFF',
    # Build the plasma object store along with Arrow
    'ARROW_PLASMA': 'OFF',
    # Build the plasma object store java client
    'ARROW_PLASMA_JAVA_CLIENT': 'OFF',
    # Rely on Protocol Buffers shared libraries where relevant
    'ARROW_PROTOBUF_USE_SHARED': 'ON',
    # Build the Arrow CPython extensions
    'ARROW_PYTHON': 'OFF',
    # How to link the re2 library. static|shared
    # 'ARROW_RE2_LINKAGE': 'static',
    # Build Arrow libraries with RATH set to $ORIGIN
    # 'ARROW_RPATH_ORIGIN': 'OFF',
    # Build Arrow with TensorFlow support enabled
    'ARROW_TENSORFLOW': 'OFF',
    # Linkage of Arrow libraries with unit tests executables. static|shared
    'ARROW_TEST_LINKAGE': 'shared',
    # Run the test suite using valgrind --tool=memcheck
    # 'ARROW_TEST_MEMCHECK': 'OFF',
    # Enable Address Sanitizer checks
    # 'ARROW_USE_ASAN': 'OFF',
    # Use ccache when compiling (if available)
    # 'ARROW_USE_CCACHE': 'ON',
    # Build libraries with glog support for pluggable logging
    # 'ARROW_USE_GLOG': 'ON',
    # Use ld.gold for linking on Linux (if available)
    # 'ARROW_USE_LD_GOLD': 'OFF',
    # Build with SIMD optimizations
    # 'ARROW_USE_SIMD': 'ON',
    # Enable Thread Sanitizer checks
    # 'ARROW_USE_TSAN': 'OFF',
    # If off, 'quiet' flags will be passed to linting tools
    # 'ARROW_VERBOSE_LINT': 'OFF',
    # If off, output from ExternalProjects will be logged to files rather
    # than shown
    'ARROW_VERBOSE_THIRDPARTY_BUILD': 'ON',
    # Build with backtrace support
    'ARROW_WITH_BACKTRACE': 'ON',
    # Build with Brotli compression
    'ARROW_WITH_BROTLI': 'ON',
    # Build with BZ2 compression
    'ARROW_WITH_BZ2': 'OFF',
    # Build with lz4 compression
    'ARROW_WITH_LZ4': 'ON',
    # Build with Snappy compression
    'ARROW_WITH_SNAPPY': 'ON',
    # Build with zlib compression
    'ARROW_WITH_ZLIB': 'ON',
    # Build with zstd compression, turned off until
    # https://issues.apache.org/jira/browse/ARROW-4831 is resolved
    'ARROW_WITH_ZSTD': 'ON',
    # Build the Parquet examples. Requires static libraries to be built.
    'PARQUET_BUILD_EXAMPLES': 'OFF',
    # Build the Parquet executable CLI tools.
    # Requires static libraries to be built.
    'PARQUET_BUILD_EXECUTABLES': 'OFF',
    # Depend only on Thirdparty headers to build libparquet.
    # Always OFF if building binaries
    'PARQUET_MINIMAL_DEPENDENCY': 'OFF'
}
definitions = {k: util.Property(k, default=v) for k, v in definitions.items()}

ld_library_path = util.Interpolate(
    '%(prop:CMAKE_INSTALL_PREFIX)s/%(prop:CMAKE_INSTALL_LIBDIR)s'
)
arrow_test_data_path = util.Interpolate(
    '%(prop:builddir)s/testing/data'
)
parquet_test_data_path = util.Interpolate(
    '%(prop:builddir)s/cpp/submodules/parquet-testing/data'
)

cpp_mkdir = Mkdir(dir='cpp/build', name='Create C++ build directory')
cpp_cmake = CMake(
    path='..',
    workdir='cpp/build',
    generator='Ninja',
    definitions=definitions
)
cpp_compile = Ninja(name='Compile C++', workdir='cpp/build')
cpp_test = CTest(args=['--output-on-failure'], workdir='cpp/build')
cpp_install = Ninja(args=['install'], name='Install C++', workdir='cpp/build')

python_install = SetupPy(
    args=['develop'],
    name='Build PyArrow',
    workdir='python',
    env={
        'ARROW_HOME': util.Property('CMAKE_INSTALL_PREFIX'),
        'PYARROW_CMAKE_GENERATOR': util.Property('CMAKE_GENERATOR'),
        'PYARROW_BUILD_TYPE': util.Property('CMAKE_BUILD_TYPE'),
        'PYARROW_WITH_ORC': util.Property('ARROW_ORC'),
        'PYARROW_WITH_CUDA': util.Property('ARROW_CUDA'),
        'PYARROW_WITH_FLIGHT': util.Property('ARROW_FLIGHT'),
        'PYARROW_WITH_PLASMA': util.Property('ARROW_PLASMA'),
        'PYARROW_WITH_GANDIVA': util.Property('ARROW_GANDIVA'),
        'PYARROW_WITH_PARQUET': util.Property('ARROW_PARQUET'),
    }
)
python_test = PyTest(
    name='Test PyArrow',
    args=['pyarrow'],
    workdir='python',
    env={'LD_LIBRARY_PATH': ld_library_path}
)


class UrsabotTest(DockerBuilder):
    tags = ['ursabot']
    steps = [
        GitHub(
            name='Clone Ursabot',
            repourl=util.Property('repository'),
            mode='full'
        ),
        Pip(['install', '-e', '.']),
        PyTest(args=['-m', 'not docker', 'ursabot']),
        ShellCommand(
            command=['flake8', 'ursabot'],
            name='Flake8'
        ),
        ShellCommand(
            command=['buildbot', 'checkconfig', '.'],
            env={'URSABOT_ENV': 'test'},
            name='Checkconfig'
        )
    ]
    images = images.filter(
        name='ursabot',
        tag='worker'
    )


class CrossbowBuilder(DockerBuilder):
    tags = ['crossbow']
    steps = [
        GitHub(
            name='Clone Arrow',
            repourl=util.Property('repository'),
            workdir='arrow',
            mode='full'
        ),
        GitHub(
            name='Clone Crossbow',
            # TODO(kszucs): read it from the comment and set as a property
            repourl='https://github.com/ursa-labs/crossbow',
            workdir='crossbow',
            branch='master',
            mode='full',
            # quite misleasing option, but it prevents checking out the branch
            # set in the sourcestamp by the pull request, which refers to arrow
            alwaysUseLatest=True
        )
    ]
    images = images.filter(
        name='crossbow',
        tag='worker'
    )


class CrossbowTrigger(CrossbowBuilder):
    steps = CrossbowBuilder.steps + [
        Crossbow(
            args=util.FlattenList([
                '--github-token', util.Secret('ursabot/github_token'),
                'submit',
                '--output', 'job.yml',
                '--job-prefix', 'ursabot',
                '--arrow-remote', util.Property('repository'),
                util.Property('crossbow_args', [])
            ]),
            workdir='arrow/dev/tasks',
            result_file='job.yml'
        )
    ]


class CrossbowStatus(CrossbowBuilder):
    steps = CrossbowBuilder.steps + [
        Crossbow(
            args=[
                '--github-token', util.Secret('ursabot/github_token'),
                'status',
                '--output', 'status.txt',
                '--job-prefix', 'nightly',
            ],
            workdir='arrow/dev/tasks',
            result_file='status.txt'
        )
    ]


# TODO(kszucs): properly implement it
# class UrsabotDockerBuild(Builder):
#     name = 'ursabot-docker-build'
#     steps = [
#         PythonFunction(lambda: 'trying to run this function')
#     ]


class ArrowCppTest(DockerBuilder):
    tags = ['arrow', 'cpp']
    properties = {
        'ARROW_PLASMA': 'ON',
        'CMAKE_INSTALL_PREFIX': '/usr/local',
        'CMAKE_INSTALL_LIBDIR': 'lib'
    }
    steps = [
        checkout_arrow,
        cpp_mkdir,
        cpp_cmake,
        cpp_compile,
        cpp_test
    ]
    images = (
        images.filter(
            name='cpp',
            arch='amd64',
            os=startswith('ubuntu'),
            variant=None,  # plain linux images, not conda
            tag='worker'
        ) +
        images.filter(
            name='cpp',
            arch='arm64v8',
            os='ubuntu-18.04',
            variant=None,  # plain linux images, not conda
            tag='worker'
        )
    )


class ArrowCppCudaTest(ArrowCppTest):
    tags = ['arrow', 'cpp', 'cuda']
    hostconfig = {
        'runtime': 'nvidia'
    }
    properties = {
        'ARROW_CUDA': 'ON',
        'ARROW_PLASMA': 'ON',
        'CMAKE_INSTALL_PREFIX': '/usr/local',
        'CMAKE_INSTALL_LIBDIR': 'lib'
    }
    images = images.filter(
        name='cpp',
        arch='amd64',
        variant='cuda',
        tag='worker'
    )


class ArrowCppBenchmark(DockerBuilder):
    tags = ['arrow', 'cpp', 'benchmark']
    properties = {
        'ARROW_PLASMA': 'ON',
        'CMAKE_INSTALL_PREFIX': '/usr/local',
        'CMAKE_INSTALL_LIBDIR': 'lib'
    }
    steps = [
        checkout_arrow,
        Pip(['install', '-e', '.'], workdir='dev/archery'),
        Archery(
            args=util.FlattenList([
                'benchmark',
                'diff',
                '--output=diff.json',
                util.Property('benchmark_options', []),
                'WORKSPACE',
                util.Property('benchmark_baseline', 'master')
            ]),
            result_file='diff.json'
        )
    ]
    images = images.filter(
        name='cpp-benchmark',
        os=startswith('ubuntu'),
        arch='amd64',  # until ARROW-5382: SSE on ARM NEON gets resolved
        variant=None,  # plain linux images, not conda
        tag='worker'
    )


class ArrowPythonTest(DockerBuilder):
    tags = ['arrow', 'python']
    hostconfig = {
        'shm_size': '2G',  # required for plasma
    }
    properties = {
        'ARROW_PYTHON': 'ON',
        'ARROW_PLASMA': 'ON',  # also sets PYARROW_WITH_PLASMA
        'CMAKE_INSTALL_PREFIX': '/usr/local',
        'CMAKE_INSTALL_LIBDIR': 'lib'
    }
    steps = [
        checkout_arrow,
        cpp_mkdir,
        cpp_cmake,
        cpp_compile,
        cpp_install,
        python_install,
        python_test
    ]
    images = (
        images.filter(
            name=startswith('python'),
            arch='amd64',
            os=startswith('ubuntu'),
            variant=None,  # plain linux images, not conda
            tag='worker'
        ) +
        images.filter(
            name=startswith('python'),
            arch='arm64v8',
            os='ubuntu-18.04',
            variant=None,  # plain linux images, not conda
            tag='worker'
        )
    )


class ArrowPythonCudaTest(ArrowPythonTest):
    tags = ['arrow', 'python', 'cuda']
    hostconfig = {
        'shm_size': '2G',  # required for plasma
        'runtime': 'nvidia',  # required for cuda
    }
    properties = {
        'ARROW_PYTHON': 'ON',
        'ARROW_CUDA': 'ON',  # also sets PYARROW_WITH_CUDA
        'ARROW_PLASMA': 'ON',  # also sets PYARROW_WITH_PLASMA
        'CMAKE_INSTALL_PREFIX': '/usr/local',
        'CMAKE_INSTALL_LIBDIR': 'lib'
    }
    images = images.filter(
        name=startswith('python'),
        arch='amd64',
        variant='cuda',
        tag='worker'
    )


class ArrowCppCondaTest(DockerBuilder):
    tags = ['arrow', 'cpp']
    properties = {
        'ARROW_FLIGHT': 'ON',
        'ARROW_PLASMA': 'ON',
        'ARROW_PARQUET': 'ON',
        'CMAKE_INSTALL_LIBDIR': 'lib'
    }
    env = {
        'ARROW_TEST_DATA': arrow_test_data_path,  # for flight
        'PARQUET_TEST_DATA': parquet_test_data_path  # for parquet
    }
    steps = [
        SetPropertiesFromEnv({
            'CMAKE_AR': 'AR',
            'CMAKE_RANLIB': 'RANLIB',
            'CMAKE_INSTALL_PREFIX': 'CONDA_PREFIX',
            'ARROW_BUILD_TOOLCHAIN': 'CONDA_PREFIX'
        }),
        checkout_arrow,
        cpp_mkdir,
        cpp_cmake,
        cpp_compile,
        cpp_test
    ]
    images = images.filter(
        name='cpp',
        variant='conda',
        tag='worker'
    )


class ArrowPythonCondaTest(DockerBuilder):
    tags = ['arrow', 'python']
    hostconfig = {
        'shm_size': '2G',  # required for plasma
    }
    properties = {
        'ARROW_FLIGHT': 'ON',
        'ARROW_PYTHON': 'ON',
        'ARROW_PLASMA': 'ON',
        'ARROW_PARQUET': 'ON',
        'CMAKE_INSTALL_LIBDIR': 'lib'
    }
    env = {
        'ARROW_TEST_DATA': arrow_test_data_path,  # for flight
        'PARQUET_TEST_DATA': parquet_test_data_path  # for parquet
    }
    steps = [
        SetPropertiesFromEnv({
            'CMAKE_AR': 'AR',
            'CMAKE_RANLIB': 'RANLIB',
            'CMAKE_INSTALL_PREFIX': 'CONDA_PREFIX',
            'ARROW_BUILD_TOOLCHAIN': 'CONDA_PREFIX'
        }),
        checkout_arrow,
        cpp_mkdir,
        cpp_cmake,
        cpp_compile,
        cpp_install,
        python_install,
        python_test
    ]
    images = images.filter(
        name=startswith('python'),
        variant='conda',
        tag='worker'
    )


class ArrowJavaTest(DockerBuilder):
    tags = ['arrow', 'java']
    steps = [
        checkout_arrow,
        Maven(
            args=['-B', 'test'],
            workdir='java',
            name='Maven Test',
        )
    ]
    images = images.filter(
        name=startswith('java'),
        arch='amd64',
        tag='worker'
    )
