from ursabot.steps import ShellCommand, ResultLogMixin


class Ninja(ShellCommand):
    # TODO(kszucs): add proper descriptions
    name = 'Ninja'
    command = ['ninja']

    def __init__(self, *targets, **kwargs):
        args = []
        for ninja_option in {'j', 'k', 'l', 'n'}:
            value = kwargs.pop(ninja_option, None)
            if value is not None:
                args.extend([f'-{ninja_option}', value])
        args.extend(targets)
        super().__init__(args=args, **kwargs)


class CTest(ShellCommand):
    name = 'CTest'
    command = ['ctest']

    def __init__(self, output_on_failure=False, **kwargs):
        args = []
        if output_on_failure:
            args.append('--output-on-failure')
        for ctest_option in {'j', 'L', 'R', 'E'}:
            value = kwargs.pop(ctest_option, None)
            if value is not None:
                args.extend([f'-{ctest_option}', value])
        super().__init__(args=args, **kwargs)


class Archery(ResultLogMixin, ShellCommand):
    name = 'Archery'
    command = ['archery']
    env = dict(LC_ALL='C.UTF-8', LANG='C.UTF-8')  # required for click


class Crossbow(ResultLogMixin, ShellCommand):
    name = 'Crossbow'
    command = ['python', 'crossbow.py']
    env = dict(LC_ALL='C.UTF-8', LANG='C.UTF-8')  # required for click


class Bundle(ShellCommand):
    name = 'Bundler'
    command = ['bundle']


class Maven(ShellCommand):
    name = 'Maven'
    command = ['mvn']


class Meson(ShellCommand):
    name = 'Meson'
    command = ['meson']


class Npm(ShellCommand):
    name = 'NPM'
    command = ['npm']


class Go(ShellCommand):
    name = 'Go'
    command = ['go']


class Cargo(ShellCommand):
    name = 'Cargo'
    command = ['cargo']


class R(ShellCommand):
    name = 'R'
    command = ['R']


class Make(ShellCommand):
    name = 'Make'
    command = ['make']
