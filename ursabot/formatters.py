import textwrap

import jinja2
import toolz
import numpy as np
import pandas as pd
from tabulate import tabulate
from twisted.python import log
from buildbot.process.results import Results


class Formatter:

    layout = None
    context = {}

    def __init__(self, layout=None, context=None):
        layout = layout or self.layout  # class' default
        if isinstance(layout, str):
            layout = textwrap.dedent(layout)
            self.layout = jinja2.Template(layout)
        else:
            raise ValueError('Formatter template must be an instance of str')

        self.context = toolz.merge(context or {}, self.context)

    async def render(self, build, master=None):
        result = Results[build['results']]
        method = getattr(self, f'render_{result}')

        try:
            context = method(build, master)
        except NotImplementedError:
            raise ValueError(
                f'Not implemented formatter for result `{result}`'
            )
        else:
            context = toolz.merge(context, self.context)

        return self.layout.render(**context)

    def render_success(self, build, master):
        raise NotImplementedError()

    def render_warnings(self, build, master):
        raise NotImplementedError()

    def render_skipped(self, build, master):
        raise NotImplementedError()

    def render_exception(self, build, master):
        raise NotImplementedError()

    def render_cancelled(self, build, master):
        raise NotImplementedError()

    def render_failure(self, build, master):
        raise NotImplementedError()

    def render_retry(self, build, master):
        raise NotImplementedError()


class GitHubCommentFormatter(Formatter):

    layout = "{{ message }}"

    def render_success(self, build, master):
        return dict(message='success')

    def render_warnings(self, build, master):
        return dict(message='warnings')

    def render_skipped(self, build, master):
        return dict(message='skipped')

    def render_exception(self, build, master):
        return dict(message='exception')

    def render_cancelled(self, build, master):
        return dict(message='cancelled')

    def render_failure(self, build, master):
        return dict(message='failure')

    def render_retry(self, build, master):
        return dict(message='retry')


class BenchmarkCommentFormatter(GitHubCommentFormatter):

    def _extract_result_logs(self, build):
        results = {}
        for s in build['steps']:
            for l in s['logs']:
                if l['name'] == 'result':
                    results[s['stepid']] = l['content']['content']
        return results

    def _render_table(self, content):
        """Renders the json content

        As a plaintext table embedded in a diff markdown snippet.
        """
        df = pd.read_json(content, lines=True)
        columns = ['benchmark', 'baseline', 'contender', 'change']
        formatted = tabulate(df[columns], headers='keys', tablefmt='rst',
                             showindex=False)

        diff = np.where(df['regression'], '-', ' ')
        # prepend and append because of header and footer
        diff = np.concatenate(([' '] * 3, diff, [' ']))

        rows = map(' '.join, zip(diff, formatted.splitlines()))
        table = '\n'.join(rows)

        return f'```diff\n{table}\n```'

    def render_success(self, build, master):
        results = self._extract_result_logs(build)
        try:
            # decode jsonlines objects and render the results as markdown table
            tables = toolz.valmap(self._render_table, results)
        except Exception as e:
            # TODO(kszucs): nicer message
            log.err(e)
            raise

        message = '\n\n'.join(tables.values())
        return dict(message=message)
