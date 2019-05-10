import textwrap

import jinja2
import toolz

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
        # title = f"{build['builder']['name']} #{build['number']}"
        # if not build['complete']:
        #     raise ValueError(f'Build {title} has not completed yet')

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

    # TODO(kszucs): implement reasonable default methods
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

    layout = """
        {{ message }}
    """

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

    def _render_table_pandas(self, content):
        import pandas as pd
        from pynliner import Pynliner

        def red_regression(row):
            color = 'red' if row['regression'] else 'black'
            return [f'color: {color}' for v in row]

        df = pd.read_json(content, lines=True)
        s = df.style.apply(red_regression, axis=1)

        # convert to style to inline css
        html = s.render()
        inlined = Pynliner().from_string(html).run()

        return inlined

    def _render_table_tabulate(self, content):
        import json
        from tabulate import tabulate

        rows = list(map(json.loads, content.splitlines()))
        return tabulate(rows, headers='keys', tablefmt='github',
                        floatfmt='.4f')

    def render_success(self, build, master):
        results = self._extract_result_logs(build)
        try:
            # decode jsonlines objects and render the results as markdown table
            tables = toolz.valmap(self._render_table_pandas, results)
        except Exception as e:
            # TODO(kszucs): nicer message
            log.err(e)
            raise

        message = '\n\n'.join(tables.values())
        return dict(message=message)
