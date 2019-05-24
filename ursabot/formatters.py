import json
import textwrap

import toolz
from tabulate import tabulate
from buildbot.util.logger import Logger
from buildbot.reporters import utils
from buildbot.process.results import Results, FAILURE, EXCEPTION


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

    def extract_logs(self, build, logname):
        # stream type prefixes each line with the stream's abbreviation:
        stream_prefixes = {
            's': 'stdout',
            'e': 'stderr',
            'h': 'header'
        }
        for s in build['steps']:
            for l in s['logs']:
                if l['name'] == logname:
                    typ = l['type']
                    lines = l['content']['content'].splitlines()

                    if typ == 'h':  # HTML
                        lines = [('html', line) for line in lines]
                    elif typ == 't':  # text
                        lines = [('text', line) for line in lines]
                    elif typ == 's':  # stream
                        lines = [(stream_prefixes[line[0]], line[1:])
                                 for line in lines]
                    else:
                        raise ValueError(f'Unknown log type: `{typ}`')

                    yield (s, lines)

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

        return self.layout.format(**context).strip()

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


# try to retrieve err.html log's content

class MarkdownFormatter(Formatter):

    layout = textwrap.dedent("""
        [{builder_name}]({build_url}) builder {status}.

        Revision: {revision}

        {context}
    """)

    def render_failure(self, build, master):
        template = textwrap.dedent("""
            {step_name}: `{state_string}` step's stderr:
            ```
            {stderr}
            ```
        """)

        # extract stderr from logs named `stdio` from failing steps
        errors = []
        for step, log_lines in self.extract_logs(build, logname='stdio'):
            if step['results'] == FAILURE:
                stderr = [l for stream, l in log_lines if stream == 'stderr']
                errors.append(
                    template.format(
                        step_name=step['name'],
                        state_string=step['state_string'],
                        stderr='\n'.join(stderr)
                    )
                )

        return dict(status='has been failed', context='\n\n'.join(errors))

    def render_exception(self, build, master):
        template = textwrap.dedent("""
            {step_name}: `{state_string}` step's traceback:
            ```pycon
            {traceback}
            ```
        """)

        # steps failed with an exception usually have a log named 'err.text',
        # which contains a HTML formatted stack traceback.
        errors = []
        for step, log_lines in self.extract_logs(build, logname='err.text'):
            if step['results'] == EXCEPTION:
                traceback = [l for _, l in log_lines]
                errors.append(
                    template.format(
                        step_name=step['name'],
                        state_string=step['state_string'],
                        traceback='\n'.join(traceback)
                    )
                )

        return dict(
            status='has been failed with an exception',
            context='\n\n'.join(errors)
        )

    def render_started(self, build, master):
        return dict(status='is started', context='')

    def render_success(self, build, master):
        return dict(status='has been succeeded', context='')

    def render_warnings(self, build, master):
        return dict(status='has been succeeded with warnings', context='')

    def render_skipped(self, build, master):
        return dict(status='was skipped', context='')

    def render_cancelled(self, build, master):
        return dict(status='was cancelled', context='')

    def render_retry(self, build, master):
        return dict(status='is retried', context='')


class BenchmarkCommentFormatter(MarkdownFormatter):

    def _render_table(self, lines):
        """Renders the json content of a result log

        As a plaintext table embedded in a diff markdown snippet.
        """
        rows = [json.loads(line.strip()) for line in lines if line]

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
        for step, log_lines in self.extract_logs(build, logname='result'):
            results[step['stepid']] = [line for _, line in log_lines]
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
        return dict(status='has been succeeded', context=context)
