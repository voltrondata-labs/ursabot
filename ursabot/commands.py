import shlex
# from functools import partial

import click
import toolz


class CommandError(Exception):

    def __init__(self, message):
        self.message = message


#
# class _CallableMixin:
#
#     def __call__(self, message):
#         args = shlex.split(message)
#         print(args)
#         try:
#             with self.make_context(None, args) as ctx:
#                 result = self.invoke(ctx)
#         except click.UsageError as e:
#             raise CommandError(e.format_message())
#
#
# class Command(_CallableMixin, click.Command):
#     pass
#
#     # def show_help(ctx, param, value):
#     #     if value and not ctx.resilient_parsing:
#     #         echo(ctx.get_help(), color=ctx.color)
#     #         ctx.exit()
#     #     return Option(help_options, is_flag=True,
#     #                   is_eager=True, expose_value=False,
#     #                   callback=show_help,
#     #                   help='Show this message and exit.')
#
#
# class Group(_CallableMixin, click.Group):
#
#     def command(self, *args, cls=None, **kwargs):
#         cls = cls or self.__class__
#         return super().command(*args, cls=cls, **kwargs)
#
#     def group(self, *args, cls=None, **kwargs):
#         cls = cls or self.__class__
#         return super().group(*args, cls=cls, **kwargs)
#
#
# command = partial(click.command, cls=Command)
# group = partial(click.group, cls=Group)
group = click.group


merge = toolz.merge


@group()
@click.pass_context
def ursabot(ctx):
    """Ursabot"""
    ctx.obj = dict()


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
    args = ['submit', '-c', 'tests.yml']
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
    args = ['submit', '-c', 'tasks.yml']
    for group in groups:
        args.extend(['-g', group])
    return {'crossbow_args': args, **props}


def ursabot_comment_handler(message):
    """Implements the API required for GithubHook"""
    args = shlex.split(message)
    try:
        return ursabot(args=args, prog_name='ursabot', standalone_mode=False)
    except click.UsageError as e:
        raise CommandError(e.format_message())
