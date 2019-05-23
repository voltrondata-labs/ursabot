import json
import textwrap

import toolz
from tabulate import tabulate
from buildbot.util.logger import Logger
from buildbot.reporters import utils
from buildbot.process.results import Results, FAILURE


log = Logger()


class Formatter:
    """Base class to render arbitrary formatted/templated messages

    Parameters
    ----------
    layout : str, default None
        string template used as a layout for the message
    context : dict, default None
        variables passed to the layout
    """

    # TODO(kszucs): support pathlib.Path object for layouts
    layout = '{message}'
    context = {}

    def __init__(self, layout=None, context=None):
        layout = layout or self.layout  # class' default
        if isinstance(layout, str):
            self.layout = textwrap.dedent(layout)
        else:
            raise ValueError('Formatter template must be an instance of str')

        self.context = toolz.merge(context or {}, self.context)

    def default_context(self, build, master=None):
        props = build['properties']
        context = {
            'build': build,
            'revision': props.get('revision', ['unknown'])[0],
            'worker_name': props.get('workername', ['unknown'])[0],
            'builder_name': props.get('buildername', ['unknown'])[0],
            'buildbot_url': master.config.buildbotURL,
            'build_url': utils.getURLForBuild(
                master, build['builder']['builderid'], build['number']
            )
        }
        return toolz.merge(context, self.context)

    async def render(self, build, master=None):
        """Dispatches and renders the layout based on the build's results.

        Each state/result has its own method, which should return a dictionary
        of context variables which are passed for the layout rendering.

        Parameters
        ----------
        build : dict
            Details of a single buildbot build, depending on the caller it can
            contain properties, steps, logs and/or the previous build of the
            same builder. See buildbot.http.reporters.HttpStatusPushBase's
            neededDetails property.
        master : buildbot master, default None
            Master instance, can be used for further database querying.
        """
        if build['complete']:
            result = Results[build['results']]
            method = getattr(self, f'render_{result}')
        else:
            method = self.render_started

        default = self.default_context(build, master)
        context = method(build, master)
        context = toolz.merge(context, default)

        return self.layout.format(**context)

    def render_started(self, build, master):
        return dict(message='Build started.')

    def render_success(self, build, master):
        return dict(message='Build succeeded.')

    def render_warnings(self, build, master):
        return dict(message='Build has warnings.')

    def render_skipped(self, build, master):
        return dict(message='Build skipped.')

    def render_exception(self, build, master):
        return dict(message='Build failed with an exception.')

    def render_cancelled(self, build, master):
        return dict(message='Build has been cancelled.')

    def render_failure(self, build, master):
        return dict(message='Build failed.')

    def render_retry(self, build, master):
        return dict(message='Build is retried.')


class MarkdownFormatter(Formatter):

    layout = textwrap.dedent("""
        [{builder_name}]({build_url}) builder for {revision} has been {status}.

        {context}
    """).strip()

    def render_failure(self, build, master):
        template = textwrap.dedent("""
            {step_name}: `{state_string}` step is failed with:
            ```
            {stderr}
            ```
        """)

        # extract stderr from logs named `stdio` from failing steps
        errors = []
        for s in build['steps']:
            if s['results'] == FAILURE:
                for l in s['logs']:
                    if l['name'] == 'stdio':
                        content = l['content']['content']
                        stderr = [line[1:] for line in content.splitlines() if
                                  line.startswith('e')]
                        errors.append(template.format(
                            step_name=s['name'],
                            state_string=s['state_string'],
                            stderr='\n'.join(stderr)
                        ))

        return dict(status='failed', context='\n\n'.join(errors))

    def render_exception(self, build, master):
        return dict(status='failed with an exception', context='')

    def render_started(self, build, master):
        return dict(status='started', context='')

    def render_success(self, build, master):
        return dict(status='succeeded', context='')

    def render_warnings(self, build, master):
        return dict(status='succeeded with warnings', context='')

    def render_skipped(self, build, master):
        return dict(status='skipped', context='')

    def render_cancelled(self, build, master):
        return dict(status='cancelled', context='')

    def render_retry(self, build, master):
        return dict(status='retried', context='')


class BenchmarkCommentFormatter(MarkdownFormatter):

    def _render_table(self, content):
        """Renders the json content of a result log

        As a plaintext table embedded in a diff markdown snippet.
        """
        lines = (line.strip() for line in content.strip().splitlines())
        rows = [json.loads(line) for line in lines if line]

        columns = ['benchmark', 'baseline', 'contender', 'change']
        formatted = tabulate(toolz.pluck(columns, rows),
                             headers=columns, tablefmt='rst')

        diff = ['-' if row['regression'] else ' ' for row in rows]
        # prepend and append because of header and footer
        diff = [' '] * 3 + diff + [' ']

        rows = map(' '.join, zip(diff, formatted.splitlines()))
        table = '\n'.join(rows)

        return f'```diff\n{table}\n```'

    def render_success(self, build, master):
        # extract logs named as `result`
        results = {}
        for s in build['steps']:
            for l in s['logs']:
                if l['name'] == 'result':
                    results[s['stepid']] = l['content']['content']
        try:
            # decode jsonlines objects and render the results as markdown table
            # each step can have a result log, but in practice each builder
            # should use a single step for logging results, for more see
            # ursabot.steps.ResultLogMixin and usage at
            # ursabot.builders.ArrowCppBenchmark
            tables = toolz.valmap(self._render_table, results)
        except Exception as e:
            # TODO(kszucs): nicer message
            log.error(e)
            raise

        context = '\n\n'.join(tables.values())
        return dict(status='succeeded', context=context)
