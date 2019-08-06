# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import shlex
from functools import partial

import click

__all__ = ['CommandError', 'Command', 'Group', 'command', 'group']


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
