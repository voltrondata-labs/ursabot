from buildbot.plugins import steps, util
from buildbot.process import buildstep
from buildbot.process.results import SUCCESS, FAILURE
from twisted.internet import threads

from .utils import ensure_deferred


class ShellMixin(buildstep.ShellMixin):
    """Run command in a login bash shell

    ShellCommand uses the old-style API but commands like CMake uses the
    new style, ShellMixin based API. Buildbot runs each command with a
    non-login /bin/sh, thus .bashrc is not loaded.

    The primary purpose of this mixin to use with conda environments.
    """

    shell = tuple()  # will run sh on unix and batch on windows by default
    command = tuple()

    def makeRemoteShellCommand(self, **kwargs):
        import pipes  # only available on unix

        def quote(e):  # copied from buildbot_worker.runprocess
            if not e:
                return '""'
            return pipes.quote(e)

        # follow the semantics of the parent method, but don't flatten
        # command = self.command + kwargs.pop('command', tuple())
        command = tuple(kwargs.pop('command'))

        if self.shell:
            # render the command and prepend with the shell
            # TODO(kszucs) validate self.shell
            command = ' '.join(map(quote, command))
            command = self.shell + (command,)

        return super().makeRemoteShellCommand(command=command, **kwargs)


class ShellCommand(ShellMixin, buildstep.BuildStep):

    def __init__(self, command=tuple(), **kwargs):
        # command should be validated during the construction
        if not isinstance(command, (tuple, list)):
            raise ValueError('Command must be an instance of list or tuple')

        # appends to the class' command to allow creating command's like
        # SetupPy via subclassing ShellCommand
        command = tuple(self.command) + tuple(command)
        if not command:
            raise ValueError('No command was provided')

        kwargs['command'] = command
        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)

    @ensure_deferred
    async def run(self):
        cmd = await self.makeRemoteShellCommand(command=self.command)
        await self.runCommand(cmd)
        return cmd.results()


# class BashMixin(ShellMixin):
#     """Runs command in an interactive bash session"""
#     # TODO(kszucs): validate that the platform is unix
#     usePTY = True
#     shell = ('/bin/bash', '-l', '-i', '-c')
#
#
# class BashCommand(BashMixin, ShellCommand):
#     pass

# class SetupPy(ShellCommand):
#     command = ['python', 'setup.py']


class CMake(ShellMixin, steps.CMake):

    name = 'CMake'

    @ensure_deferred
    async def run(self):
        """Create and run CMake command

        Copied from the original CMake implementation to handle None values as
        missing ones.
        """
        command = [self.cmake]

        if self.generator:
            command.extend(['-G', self.generator])
        if self.path:
            command.append(self.path)

        if self.definitions is not None:
            for k, v in self.definitions.items():
                # handle None values as missing
                if v is not None:
                    command.append(f'-D{k}={v}')

        if self.options is not None:
            command.extend(self.options)

        cmd = await self.makeRemoteShellCommand(command=command)
        await self.runCommand(cmd)

        return cmd.results()


class ShowEnv(ShellCommand):
    name = 'ShowEnv'
    command = ['env']


class SetPropertiesFromEnv(buildstep.BuildStep):
    """Sets properties from environment variables on the worker."""

    name = 'SetPropertiesFromEnv'
    description = ['Setting']
    descriptionDone = ['Set']

    def __init__(self, variables, source='WorkerEnvironment', **kwargs):
        self.variables = variables
        self.source = source
        super().__init__(**kwargs)

    @ensure_deferred
    async def run(self):
        # on Windows, environment variables are case-insensitive, but we have
        # a case-sensitive dictionary in worker_environ.  Fortunately, that
        # dictionary is also folded to uppercase, so we can simply fold the
        # variable names to uppercase to duplicate the case-insensitivity.
        fold_to_uppercase = (self.worker.worker_system == 'win32')

        properties = self.build.getProperties()
        environ = self.worker.worker_environ

        for prop, var in self.variables.items():
            if fold_to_uppercase:
                var = var.upper()

            value = environ.get(var, None)
            if value:
                # note that the property is not uppercased

                # TODO(kszucs) try with self.setProperty similarly like in
                # SetProperties
                properties.setProperty(prop, value, self.source, runtime=True)
                await self.addCompleteLog('set-prop', f'{prop}: {value}')

        return SUCCESS


class PythonFunction(buildstep.BuildStep):
    """Executes arbitrary python function."""

    name = 'PythonFunction'
    description = ['Executing']
    descriptionDone = ['Executed']

    def __init__(self, fn, **kwargs):
        self.fn = fn
        super().__init__(**kwargs)

    @ensure_deferred
    async def run(self):
        try:
            result = await threads.deferToThread(self.fn)
        except Exception as e:
            await self.addLogWithException(e)
            return FAILURE
        else:
            await self.addCompleteLog('result', result)
            return SUCCESS


checkout = steps.Git(
    name='Clone Arrow',
    repourl='https://github.com/apache/arrow',
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
    # 'ARROW_BUILD_SHARED': 'ON',
    # Build static libraries
    # 'ARROW_BUILD_STATIC': 'ON',
    # Build the Arrow googletest unit tests
    'ARROW_BUILD_TESTS': 'ON',
    # Build Arrow commandline utilities
    # 'ARROW_BUILD_UTILITIES': 'ON',
    # Build the Arrow Compute Modules
    # 'ARROW_COMPUTE': 'ON',
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
    # 'ARROW_GANDIVA': 'OFF',
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
    # 'ARROW_JEMALLOC': 'ON',
    # Exclude deprecated APIs from build
    # 'ARROW_NO_DEPRECATED_API': 'OFF',
    # Only define the lint and check-format targets
    # 'ARROW_ONLY_LINT': 'OFF',
    # If enabled install ONLY targets that have already been built.
    # Please be advised that if this is enabled 'install' will fail silently
    # on components that have not been built.
    # 'ARROW_OPTIONAL_INSTALL': 'OFF',
    # Build the Arrow ORC adapter
    # 'ARROW_ORC': 'OFF',
    # Build the Parquet libraries
    'ARROW_PARQUET': 'OFF',
    # Build the plasma object store along with Arrow
    # 'ARROW_PLASMA': 'OFF',
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
    # 'ARROW_WITH_BROTLI': 'ON',
    # Build with BZ2 compression
    # 'ARROW_WITH_BZ2': 'OFF',
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


conda_props = SetPropertiesFromEnv({
    'CMAKE_AR': 'AR',
    'CMAKE_RANLIB': 'RANLIB',
    'CMAKE_INSTALL_PREFIX': 'CONDA_PREFIX',
    'ARROW_BUILD_TOOLCHAIN': 'CONDA_PREFIX'
})

mkdir = steps.MakeDirectory(
    name='Create C++ build directory',
    dir='cpp/build'
)

cmake = CMake(
    path='..',
    workdir='cpp/build',
    generator=util.Property('CMAKE_GENERATOR', default='Ninja'),
    definitions=definitions
)


class Ninja(ShellCommand):
    # TODO(kszucs): add proper descriptions
    name = 'Ninja'
    command = ['ninja']


class SetupPy(ShellCommand):
    name = 'setup.py'
    command = ['python', 'setup.py']


# TODO(kszucs): use property
compile = Ninja(name='Compile C++', workdir='cpp/build')
test = Ninja(['test'], name='Test C++', workdir='cpp/build')
install = Ninja(['install'], name='Install C++', workdir='cpp/build')

setup = SetupPy(
    command=['build_ext', '--inplace'],
    name='Build Python Extension',
    workdir='python',
    env={
        'ARROW_HOME': util.Property('CMAKE_INSTALL_PREFIX'),
        'PYARROW_CMAKE_GENERATOR': util.Property('CMAKE_GENERATOR'),
        'PYARROW_BUILD_TYPE': util.Property('CMAKE_BUILD_TYPE'),
        'PYARROW_WITH_PARQUET': util.Property('ARROW_PARQUET')
    }
)

pytest = ShellCommand(
    name='Run Pytest',
    command=['pytest', '-v', 'pyarrow'],
    workdir='python'
)

env = ShowEnv()

ls = ShellCommand(
    name='List files',
    command=['ls', '-lah'],
    workdir='.'
)

cpp_props = steps.SetProperties({
    'CMAKE_INSTALL_PREFIX': '/usr/local'
})

python_props = steps.SetProperties({
    'ARROW_PYTHON': 'ON',
    'ARROW_PLASMA': 'ON'
})
