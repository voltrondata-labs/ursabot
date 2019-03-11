from twisted.internet import defer

from buildbot.plugins import steps, util
from buildbot.process import buildstep


class ShellMixin(buildstep.ShellMixin):
    """Run command in a login bash shell

    ShellCommand uses the old-style API but commands like CMake uses the
    new style, ShellMixin based API. Buildbot runs each command with a
    non-login /bin/sh, thus .bashrc is not loaded.

    The primary purpose of this mixin to use with conda environments.
    """

    shell = tuple()  # will run sh on unix and batch on windows

    def makeRemoteShellCommand(self, **kwargs):
        import pipes  # only available on unix

        def quote(e):  # copied from buildbot_worker.runprocess
            if not e:
                return '""'
            return pipes.quote(e)

        # follow the semantics of the parent method, but don't flatten
        command = kwargs.pop('command', self.command)

        # command should be validated during the construction
        if isinstance(command, (tuple, list)):
            command = tuple(command)
        else:
            raise ValueError('Command must be an instance of list or tuple')

        # render the command and prepend with the shell
        command = ' '.join(map(quote, command))
        command = self.shell + (command,)  # TODO(kszucs) validate self.shell

        return super().makeRemoteShellCommand(command=command, **kwargs)


class ShellCommand(ShellMixin, buildstep.BuildStep):

    def __init__(self, **kwargs):
        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand(command=self.command)
        yield self.runCommand(cmd)
        return cmd.results()


class BashMixin(ShellMixin):
    # TODO(kszucs): validate that the platform is unix
    usePTY = True
    shell = ('/bin/bash', '-l', '-i', '-c')
    haltOnFailure = True


class BashCommand(BashMixin, ShellCommand):
    pass


class CMake(BashMixin, steps.CMake):
    pass


checkout = steps.Git(
    repourl='https://github.com/apache/arrow',
    mode='incremental',
    submodules=True
)

# -DCMAKE_INSTALL_PREFIX=build
# -DCMAKE_INSTALL_LIBDIR=lib
# -DARROW_INSTALL_NAME_RPATH=ON
# -DCMAKE_CXX_FLAGS

# explicitly define build definitions, exported via cmake -LAH
flags = {
    # Build type
    'CMAKE_BUILD_TYPE': 'debug',
    # AR path, required for conda builds
    # 'CMAKE_AR': '${AR}',
    # RUNLIB path, required for conda builds
    # 'CMAKE_RANLIB': '${RANLIB}',
    # Build Arrow with Altivec
    'ARROW_ALTIVEC': 'ON',
    # Rely on boost shared libraries where relevant
    'ARROW_BOOST_USE_SHARED': 'ON',
    # Use vendored Boost instead of existing Boost.
    # Note that this requires linking Boost statically.
    'ARROW_BOOST_VENDORED': 'OFF',
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
    'ARROW_EXTRA_ERROR_CONTEXT': 'OFF',
    # Build the Arrow Flight RPC System (requires GRPC, Protocol Buffers)
    'ARROW_FLIGHT': 'OFF',
    # Build Arrow Fuzzing executables
    'ARROW_FUZZING': 'OFF',
    # Build the Gandiva libraries
    'ARROW_GANDIVA': 'OFF',
    # Build the Gandiva JNI wrappers
    'ARROW_GANDIVA_JAVA': 'OFF',
    # Compiler flags to append when pre-compiling Gandiva operations
    'ARROW_GANDIVA_PC_CXX_FLAGS': '',
    # Include -static-libstdc++ -static-libgcc when linking with Gandiva
    # static libraries
    'ARROW_GANDIVA_STATIC_LIBSTDCPP': 'OFF',
    # Build with C++ code coverage enabled
    'ARROW_GENERATE_COVERAGE': 'OFF',
    # Rely on GFlags shared libraries where relevant
    'ARROW_GFLAGS_USE_SHARED': 'ON',
    # Pass -ggdb flag to debug builds
    'ARROW_GGDB_DEBUG': 'ON',
    # Build the Arrow HDFS bridge
    'ARROW_HDFS': 'ON',
    # Build the HiveServer2 client and Arrow adapter
    'ARROW_HIVESERVER2': 'OFF',
    # Build Arrow libraries with install_name set to @rpath
    'ARROW_INSTALL_NAME_RPATH': 'ON',
    # Build the Arrow IPC extensions
    'ARROW_IPC': 'ON',
    # Build the Arrow jemalloc-based allocator
    'ARROW_JEMALLOC': 'ON',
    # Exclude deprecated APIs from build
    'ARROW_NO_DEPRECATED_API': 'OFF',
    # Only define the lint and check-format targets
    'ARROW_ONLY_LINT': 'OFF',
    # If enabled install ONLY targets that have already been built.
    # Please be advised that if this is enabled 'install' will fail silently
    # on components that have not been built.
    'ARROW_OPTIONAL_INSTALL': 'OFF',
    # Build the Arrow ORC adapter
    'ARROW_ORC': 'OFF',
    # Build the Parquet libraries
    'ARROW_PARQUET': 'OFF',
    # Build the plasma object store along with Arrow
    'ARROW_PLASMA': 'OFF',
    # Build the plasma object store java client
    'ARROW_PLASMA_JAVA_CLIENT': 'OFF',
    # Rely on Protocol Buffers shared libraries where relevant
    'ARROW_PROTOBUF_USE_SHARED': 'OFF',
    # Build the Arrow CPython extensions
    'ARROW_PYTHON': 'OFF',
    # How to link the re2 library. static|shared
    'ARROW_RE2_LINKAGE': 'static',
    # Build Arrow libraries with RATH set to $ORIGIN
    'ARROW_RPATH_ORIGIN': 'OFF',
    # Build Arrow with TensorFlow support enabled
    'ARROW_TENSORFLOW': 'OFF',
    # Linkage of Arrow libraries with unit tests executables. static|shared
    'ARROW_TEST_LINKAGE': 'shared',
    # Run the test suite using valgrind --tool=memcheck
    'ARROW_TEST_MEMCHECK': 'OFF',
    # Enable Address Sanitizer checks
    'ARROW_USE_ASAN': 'OFF',
    # Use ccache when compiling (if available)
    'ARROW_USE_CCACHE': 'ON',
    # Build libraries with glog support for pluggable logging
    'ARROW_USE_GLOG': 'ON',
    # Use ld.gold for linking on Linux (if available)
    'ARROW_USE_LD_GOLD': 'OFF',
    # Build with SIMD optimizations
    'ARROW_USE_SIMD': 'ON',
    # Enable Thread Sanitizer checks
    'ARROW_USE_TSAN': 'OFF',
    # If off, 'quiet' flags will be passed to linting tools
    'ARROW_VERBOSE_LINT': 'OFF',
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
    'ARROW_WITH_ZSTD': 'OFF',
    # Build the Parquet examples. Requires static libraries to be built.
    'PARQUET_BUILD_EXAMPLES': 'OFF',
    # Build the Parquet executable CLI tools.
    # Requires static libraries to be built.
    'PARQUET_BUILD_EXECUTABLES': 'OFF',
    # Depend only on Thirdparty headers to build libparquet.
    # Always OFF if building binaries
    'PARQUET_MINIMAL_DEPENDENCY': 'OFF'
}

mkdir = steps.MakeDirectory(dir='build')

cmake = CMake(
    path='cpp',
    workdir='build',
    generator=util.Property('CMAKE_GENERATOR', default='Ninja'),
    definitions={k: util.Property(k, default=v) for k, v in flags.items()}
)

# TODO(kszucs): use property
compile = BashCommand(
    command=['ninja'],
    workdir='build'
)
test = BashCommand(
    command=['ninja', 'test'],
    workdir='build'
)

env_old = steps.ShellCommand(command=['env'])
env = BashCommand(command=['env'])

ls = steps.ShellCommand(command=['ls', '-lah'])
echo = steps.ShellCommand(command=['echo', 'testing...'])

# TODO(kszucs)
# compile_python = steps.ShellCommand()
