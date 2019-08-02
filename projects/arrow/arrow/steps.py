from ursabot.steps import ShellCommand, ResultLogMixin


class Archery(ResultLogMixin, ShellCommand):
    name = 'Archery'
    command = ['archery']
    env = dict(LC_ALL='C.UTF-8', LANG='C.UTF-8')  # required for click


class Crossbow(ResultLogMixin, ShellCommand):
    name = 'Crossbow'
    command = ['python', 'crossbow.py']
    env = dict(LC_ALL='C.UTF-8', LANG='C.UTF-8')  # required for click
