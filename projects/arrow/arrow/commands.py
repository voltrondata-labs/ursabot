# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import shlex
import click

from ursabot.commands import group


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
              type=str, default=None,
              help='Regex filtering benchmark suites.')
@click.option('--benchmark-filter', metavar='<regex>', show_default=True,
              type=str, default=None,
              help='Regex filtering benchmarks.')
@click.option("--cc", metavar="<compiler>", help="C compiler.", default=None)
@click.option("--cxx", metavar="<compiler>", help="C++ compiler.",
              default=None)
@click.option("--cxx-flags", help="C++ compiler flags.", default=None)
@click.option("--repetitions", type=int, default=1, show_default=True,
              help=("Number of repetitions of each benchmark. Increasing "
                    "may improve result precision."))
def benchmark(baseline, suite_filter, benchmark_filter, cc, cxx, cxx_flags,
              repetitions):
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
    # Note that specifying the baseline is the only way to compare using a new
    # benchmark, since master does not contain the new benchmark and no
    # comparison is possible.
    #
    # The following command compares the results of matching benchmarks,
    # compiling against HEAD and the provided baseline commit, e.g. eaf8302.
    # You can use this to quantify the performance improvement of new
    # optimizations or to check for regressions.
    @ursabot benchmark --benchmark-filter=MyBenchmark eaf8302
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
    if cc:
        opts.append(f'--cc={cc}')
    if cxx:
        opts.append(f'--cxx={cxx}')
    if cxx_flags:
        opts.append(f'--cxx-flags={cxx_flags}')
    if repetitions:
        opts.append(f'--repetitions={repetitions}')

    if opts:
        props['benchmark_options'] = opts

    return props


@ursabot.group()
@click.option('--repo', '-r', default='ursa-labs/crossbow',
              help='Crossbow repository on github to use')
@click.pass_obj
def crossbow(props, repo):
    """Trigger crossbow builds for this pull request"""
    # TODO(kszucs): validate the repo format
    props['command'] = 'crossbow'
    props['crossbow_repo'] = repo  # github user/repo
    props['crossbow_repository'] = f'https://github.com/{repo}'  # git url


@crossbow.command()
@click.argument('task', nargs=-1, required=False)
@click.option('--group', '-g', multiple=True,
              help='Submit task groups as defined in tests.yml')
@click.pass_obj
def submit(props, task, group):
    """Submit crossbow testing tasks.

    See groups defined in arrow/dev/tasks/tests.yml
    """
    args = ['-c', 'tasks.yml']
    for g in group:
        args.extend(['-g', g])
    for t in task:
        args.append(t)

    return {'crossbow_args': args, **props}
