import shlex
from functools import partial

import click


class CommandError(Exception):

    def __init__(self, message):
        self.message = message


class _CommandMixin:

    def get_help_option(self, ctx):
        def show_help(ctx, param, value):
            if value and not ctx.resilient_parsing:
                raise click.UsageError(ctx.get_help())
        option = super().get_help_option(ctx)
        option.callback = show_help
        return option

    def __call__(self, message):
        args = shlex.split(message)
        try:
            with self.make_context(self.name, args=args) as ctx:
                return self.invoke(ctx)
        except click.ClickException as e:
            raise CommandError(e.format_message())


class Command(_CommandMixin, click.Command):
    pass


class Group(_CommandMixin, click.Group):

    def command(self, *args, **kwargs):
        kwargs.setdefault('cls', Command)
        return super().command(*args, **kwargs)

    def group(self, *args, **kwargs):
        kwargs.setdefault('cls', Group)
        return super().group(*args, **kwargs)

    def parse_args(self, ctx, args):
        if not args and self.no_args_is_help and not ctx.resilient_parsing:
            raise click.UsageError(ctx.get_help())
        return super().parse_args(ctx, args)


command = partial(click.command, cls=Command)
group = partial(click.group, cls=Group)


@group(name='@ursabot')
@click.pass_context
def ursabot(ctx):
    """Ursabot"""
    ctx.ensure_object(dict)


@ursabot.command()
def build():
    """Trigger all tests registered for this pull request."""
    # each command must return a dictionary which are set as build properties
    return {'command': 'build'}


@ursabot.command()
def benchmark():
    """Trigger all benchmarks registered for this pull request."""
    # each command must return a dictionary which are set as build properties
    return {'command': 'benchmark'}


@ursabot.group()
@click.pass_obj
def crossbow(props):
    """Trigger crossbow builds for this pull request"""
    props['command'] = 'crossbow'


@crossbow.command()
@click.argument('groups', nargs=-1,
                type=click.Choice(['docker', 'integration', 'cpp-python']))
@click.pass_obj
def test(props, groups):
    """Submit crossbow testing tasks.

    See groups defined in arrow/dev/tasks/tests.yml
    """
    args = ['-c', 'tests.yml']
    for group in groups:
        args.extend(['-g', group])
    return {'crossbow_args': args, **props}


@crossbow.command()
@click.argument('groups', nargs=-1,
                type=click.Choice(['conda', 'wheel', 'linux', 'gandiva']))
@click.pass_obj
def package(props, groups):
    """Submit crossbow packaging tasks.

    See groups defined in arrow/dev/tasks/tasks.yml
    """
    args = ['-c', 'tasks.yml']
    for group in groups:
        args.extend(['-g', group])
    return {'crossbow_args': args, **props}
