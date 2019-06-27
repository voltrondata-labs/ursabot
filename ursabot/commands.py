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
@click.argument('baseline', type=str, metavar='[<baseline>]', default=None,
                required=False)
@click.option('--suite-filter', metavar='<regex>', show_default=True,
              type=str, default=None, help='Regex filtering benchmark suites.')
@click.option('--benchmark-filter', metavar='<regex>', show_default=True,
              type=str, default=None,
              help='Regex filtering benchmarks.')
def benchmark(baseline, suite_filter, benchmark_filter):
    """Run the benchmark suite in comparison mode.

    This command will run the benchmark suite for tip of the branch commit
    against `<baseline>` (or master if not provided).

    Examples:

    \b
    # Run the all the benchmarks
    @ursabot benchmark

    \b
    # Compare only benchmarks where the name matches the /^Sum/ regex
    @ursabot benchmark --benchmark-filter=^Sum

    \b
    # Compare only benchmarks where the suite matches the /compute-/ regex.
    # A suite is the C++ binary.
    @ursabot benchmark --suite-filter=compute-

    \b
    # Sometimes a new optimization requires the addition of new benchmarks to
    # quantify the performance increase. When doing this be sure to add the
    # benchmark in a separate commit before introducing the optimization.
    #
    # Note that specifying the baseline is the only way to compare a new
    # benchmark, otherwise the intersection of benchmarks with master will be
    # empty (no comparison possible).
    #
    # The following command compares the results of matching benchmarks,
    # compiling against HEAD and the provided baseline commit (HEAD~2). You can
    # use this to quantify the performance improvement of new optimizations or
    # to check for regressions.
    @ursabot benchmark --benchmark-filter=MyBenchmark HEAD~2
    """
    # each command must return a dictionary which are set as build properties
    props = {'command': 'benchmark'}

    if baseline:
        props['benchmark_baseline'] = baseline

    opts = []
    if suite_filter:
        suite_filter = shlex.quote(suite_filter)
        opts.append(f'--suite-filter={suite_filter}')
    if benchmark_filter:
        benchmark_filter = shlex.quote(benchmark_filter)
        opts.append(f'--benchmark-filter={benchmark_filter}')

    if opts:
        props['benchmark_options'] = opts

    return props


@ursabot.group()
@click.pass_obj
def crossbow(props):
    """Trigger crossbow builds for this pull request"""
    props['command'] = 'crossbow'


@crossbow.command()
@click.argument('task', nargs=-1, required=False)
@click.option('--group', '-g', multiple=True,
              type=click.Choice(['docker', 'integration', 'cpp-python']),
              help='Submit task groups as defined in tests.yml')
@click.pass_obj
def test(props, task, group):
    """Submit crossbow testing tasks.

    See groups defined in arrow/dev/tasks/tests.yml
    """
    args = ['-c', 'tests.yml']
    for g in group:
        args.extend(['-g', g])
    for t in task:
        args.append(t)

    return {'crossbow_args': args, **props}


@crossbow.command()
@click.argument('task', nargs=-1, required=False)
@click.option('--group', '-g', multiple=True,
              type=click.Choice(['conda', 'wheel', 'linux', 'gandiva']),
              help='Submit task groups as defined in tasks.yml')
@click.pass_obj
def package(props, task, group):
    """Submit crossbow packaging tasks.

    See groups defined in arrow/dev/tasks/tasks.yml
    """
    args = ['-c', 'tasks.yml']
    for g in group:
        args.extend(['-g', g])
    for t in task:
        args.append(t)

    return {'crossbow_args': args, **props}
