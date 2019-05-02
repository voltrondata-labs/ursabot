from twisted.internet import threads

from buildbot.plugins import steps
from buildbot.process import buildstep
from buildbot.process.results import SUCCESS, FAILURE

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
    args = tuple()

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
            command = tuple(self.shell) + (command,)

        return super().makeRemoteShellCommand(command=command, **kwargs)


class ShellCommand(ShellMixin, buildstep.BuildStep):

    name = 'Shell'

    def __init__(self, args=tuple(), command=tuple(), **kwargs):
        # command should be validated during the construction
        if not isinstance(command, (tuple, list)):
            raise ValueError('Command must be an instance of list or tuple')
        if not isinstance(args, (tuple, list)):
            raise ValueError('Args must be an instance of list or tuple')

        # appends to the class' command to allow creating command's like
        # SetupPy via subclassing ShellCommand
        command = tuple(command or self.command) + tuple(args or self.args)
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


class Env(ShellCommand):
    name = 'Environment'
    command = ['env']


class Ninja(ShellCommand):
    # TODO(kszucs): add proper descriptions
    name = 'Ninja'
    command = ['ninja']


class SetupPy(ShellCommand):
    name = 'Setup.py'
    command = ['python', 'setup.py']


class PyTest(ShellCommand):
    name = 'PyTest'
    command = ['pytest', '-v']


class Pip(ShellCommand):
    name = 'Pip'
    command = ['pip']


Mkdir = steps.MakeDirectory
GitHub = steps.GitHub


class Archery(ShellCommand):
    name = 'Archery'
    command = ['archery']
