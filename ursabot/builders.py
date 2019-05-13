import copy
import toolz
import itertools
import warnings
from collections import defaultdict

from buildbot import interfaces
from buildbot.plugins import util
from codenamize import codenamize

from .docker import DockerImage, arrow_images, ursabot_images
from .steps import (ShellCommand, SetPropertiesFromEnv,
                    Ninja, SetupPy, CMake, PyTest, Mkdir, Pip, GitHub, Archery)
from .utils import startswith, slugify


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
                 tags=None, properties=None, default_properties=None,
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
        properties = toolz.merge(properties or {}, self.properties or {})
        default_properties = toolz.merge(default_properties or {},
                                         self.default_properties or {})
        workernames = None if workers is None else [w.name for w in workers]

        return super().__init__(name=name, tags=tags, properties=properties,
                                defaultProperties=default_properties,
                                workernames=workernames, factory=factory,
                                **kwargs)

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

    def __init__(self, name=None, image=None, properties=None, tags=None,
                 **kwargs):
        if not isinstance(image, DockerImage):
            raise ValueError('Image must be an instance of DockerImage')

        name = image.title
        tags = tags or [image.name]
        tags += list(image.platform)
        properties = properties or {}
        properties['docker_image'] = str(image)
        super().__init__(name=name, properties=properties, tags=tags, **kwargs)

    @classmethod
    def builders_for(cls, workers, images=None):
        images = images or cls.images
        workers_by_arch = workers.groupby('arch')

        builders = []
        for image in images:
            if image.arch in workers_by_arch:
                workers = workers_by_arch[image.arch]
                builder = cls(image=image, workers=workers)
                builders.append(builder)
            else:
                warnings.warn(
                    f'There are no docker workers available for architecture '
                    f'`{image.arch}`, omitting image `{image}`'
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
    # Build Arrow with Altivec
    # 'ARROW_ALTIVEC': 'ON',
    # Rely on boost shared libraries where relevant
    # 'ARROW_BOOST_USE_SHARED': 'ON',
    # Use vendored Boost instead of existing Boost.
    # Note that this requires linking Boost statically.
    # 'ARROW_BOOST_VENDORED': 'OFF',
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
    # 'ARROW_BUILD_UTILITIES': 'ON',
    # Build the Arrow Compute Modules
    'ARROW_COMPUTE': 'ON',
    # Build the Arrow CUDA extensions (requires CUDA toolkit)
    # 'ARROW_CUDA': 'OFF',
    # Compiler flags to append when compiling Arrow
    # 'ARROW_CXXFLAGS': '',
    # Compile with extra error context (line numbers, code)
    'ARROW_EXTRA_ERROR_CONTEXT': 'ON',
    # Build the Arrow Flight RPC System (requires GRPC, Protocol Buffers)
    # 'ARROW_FLIGHT': 'OFF',
    # Build Arrow Fuzzing executables
    # 'ARROW_FUZZING': 'OFF',
    # Build the Gandiva libraries
    'ARROW_GANDIVA': 'OFF',
    # Build the Gandiva JNI wrappers
    # 'ARROW_GANDIVA_JAVA': 'OFF',
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
    # 'ARROW_HDFS': 'ON',
    # Build the HiveServer2 client and Arrow adapter
    # 'ARROW_HIVESERVER2': 'OFF',
    # Build Arrow libraries with install_name set to @rpath
    # 'ARROW_INSTALL_NAME_RPATH': 'ON',
    # Build the Arrow IPC extensions
    # 'ARROW_IPC': 'ON',
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
    # 'ARROW_PLASMA_JAVA_CLIENT': 'OFF',
    # Rely on Protocol Buffers shared libraries where relevant
    # 'ARROW_PROTOBUF_USE_SHARED': 'OFF',
    # Build the Arrow CPython extensions
    'ARROW_PYTHON': 'OFF',
    # How to link the re2 library. static|shared
    # 'ARROW_RE2_LINKAGE': 'static',
    # Build Arrow libraries with RATH set to $ORIGIN
    # 'ARROW_RPATH_ORIGIN': 'OFF',
    # Build Arrow with TensorFlow support enabled
    # 'ARROW_TENSORFLOW': 'OFF',
    # Linkage of Arrow libraries with unit tests executables. static|shared
    # 'ARROW_TEST_LINKAGE': 'shared',
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
    # 'PARQUET_BUILD_EXAMPLES': 'OFF',
    # Build the Parquet executable CLI tools.
    # Requires static libraries to be built.
    # 'PARQUET_BUILD_EXECUTABLES': 'OFF',
    # Depend only on Thirdparty headers to build libparquet.
    # Always OFF if building binaries
    # 'PARQUET_MINIMAL_DEPENDENCY': 'OFF'
}
definitions = {k: util.Property(k, default=v) for k, v in definitions.items()}

ld_library_path = util.Interpolate(
    '%(prop:CMAKE_INSTALL_PREFIX)s/%(prop:CMAKE_INSTALL_LIBDIR)s'
)

cpp_mkdir = Mkdir(dir='cpp/build', name='Create C++ build directory')
cpp_cmake = CMake(
    path='..',
    workdir='cpp/build',
    generator='Ninja',
    definitions=definitions
)
cpp_compile = Ninja(name='Compile C++', workdir='cpp/build')
cpp_test = Ninja(args=['test'], name='Test C++', workdir='cpp/build')
cpp_install = Ninja(args=['install'], name='Install C++', workdir='cpp/build')

python_install = SetupPy(
    args=['develop'],
    name='Build PyArrow',
    workdir='python',
    env={
        'ARROW_HOME': util.Property('CMAKE_INSTALL_PREFIX'),
        'PYARROW_CMAKE_GENERATOR': util.Property('CMAKE_GENERATOR'),
        'PYARROW_BUILD_TYPE': util.Property('CMAKE_BUILD_TYPE'),
        'PYARROW_WITH_PARQUET': util.Property('ARROW_PARQUET')
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
        # --no-binary buildbot is required because buildbot doesn't bundle its
        # tests to binary wheels, but ursabot's test suite depends on
        # buildbot's so install it from source
        Pip(['install', '--no-binary', 'buildbot',
             'pytest', 'flake8', 'mock', '-e', '.']),
        PyTest(args=['-m', 'not docker', 'ursabot']),
        ShellCommand(command=['flake8', 'ursabot']),
        ShellCommand(command=['buildbot', 'checkconfig', '.'],
                     env={'URSABOT_ENV': 'test'})
    ]
    images = ursabot_images.filter(tag='worker')


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
    images = arrow_images.filter(
        name='cpp',
        os=startswith('ubuntu') | startswith('alpine'),
        variant=None,  # plain linux images, no conda
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
            args=['benchmark', 'diff', '--output=diff.json',
                  'WORKSPACE', 'master'],
            result_file='diff.json',
        )
    ]
    images = arrow_images.filter(
        name='cpp-benchmark',
        os=startswith('ubuntu'),
        variant=None,  # plain linux images, no conda
        tag='worker'
    )


class ArrowPythonTest(DockerBuilder):
    tags = ['arrow', 'python']
    properties = {
        'ARROW_PYTHON': 'ON',
        'ARROW_PLASMA': 'ON',
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
    images = arrow_images.filter(
        name=startswith('python'),
        os=startswith('ubuntu') | startswith('alpine'),
        variant=None,
        tag='worker'
    )


class ArrowCppCondaTest(DockerBuilder):
    tags = ['arrow', 'cpp']
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
    images = arrow_images.filter(
        name='cpp',
        variant='conda',
        tag='worker'
    )


class ArrowPythonCondaTest(DockerBuilder):
    tags = ['arrow', 'python']
    properties = {
        'ARROW_PYTHON': 'ON',
        'ARROW_PLASMA': 'ON',
        'CMAKE_INSTALL_LIBDIR': 'lib'
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
    images = arrow_images.filter(
        name=startswith('python'),
        variant='conda',
        tag='worker'
    )
