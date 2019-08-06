# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import textwrap

import toolz
from buildbot.util.logger import Logger
from buildbot.reporters import utils
from buildbot.process.results import Results, FAILURE, EXCEPTION

__all__ = ['Formatter', 'MarkdownFormatter']


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
            'build_id': build['buildid'],
            'build_url': utils.getURLForBuild(
                master, build['builder']['builderid'], build['number']
            )
        }
        return toolz.merge(context, self.context)

    def extract_logs(self, build, logname):
        # stream type prefixes each line with the stream's abbreviation:
        _stream_prefixes = {
            'o': 'stdout',
            'e': 'stderr',
            'h': 'header'
        }

        def _stream(line):
            return (_stream_prefixes[line[0]], line[1:])

        def _html(line):
            return ('html', line)

        def _text(line):
            return ('text', line)

        for s in build['steps']:
            for l in s['logs']:
                if l['name'] == logname:
                    typ = l['type']

                    if typ == 'h':  # HTML
                        extractor = _html
                    elif typ == 't':  # text
                        extractor = _text
                    elif typ == 's':  # stream
                        extractor = _stream
                    else:
                        raise ValueError(f'Unknown log type: `{typ}`')

                    content = l['content']['content']
                    lines = (extractor(l) for l in content.splitlines())

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
        context = await method(build, master)
        context = toolz.merge(context, default)

        return self.layout.format(**context).strip()

    async def render_started(self, build, master):
        return dict(message='Build started.')

    async def render_success(self, build, master):
        return dict(message='Build succeeded.')

    async def render_warnings(self, build, master):
        return dict(message='Build has warnings.')

    async def render_skipped(self, build, master):
        return dict(message='Build skipped.')

    async def render_exception(self, build, master):
        return dict(message='Build failed with an exception.')

    async def render_cancelled(self, build, master):
        return dict(message='Build has been cancelled.')

    async def render_failure(self, build, master):
        return dict(message='Build failed.')

    async def render_retry(self, build, master):
        return dict(message='Build is retried.')


class MarkdownFormatter(Formatter):

    layout = textwrap.dedent("""
        [{builder_name} (#{build_id})]({build_url}) builder {status}.

        Revision: {revision}

        {context}
    """)

    async def render_failure(self, build, master):
        template = textwrap.dedent("""
            {step_name}: `{state_string}` step's stderr:
            ```
            {stderr}
            ```
        """).strip()

        # extract stderr from logs named `stdio` from failing steps
        errors = []
        for step, log_lines in self.extract_logs(build, logname='stdio'):
            if step['results'] == FAILURE:
                stderr = (l for stream, l in log_lines if stream == 'stderr')
                errors.append(
                    template.format(
                        step_name=step['name'],
                        state_string=step['state_string'],
                        stderr='\n'.join(stderr)
                    )
                )

        return dict(status='failed', context='\n\n'.join(errors))

    async def render_exception(self, build, master):
        template = textwrap.dedent("""
            {step_name}: `{state_string}` step's traceback:
            ```pycon
            {traceback}
            ```
        """).strip()

        # steps failed with an exception usually have a log named 'err.text',
        # which contains a HTML formatted stack traceback.
        errors = []
        for step, log_lines in self.extract_logs(build, logname='err.text'):
            if step['results'] == EXCEPTION:
                traceback = (l for _, l in log_lines)
                errors.append(
                    template.format(
                        step_name=step['name'],
                        state_string=step['state_string'],
                        traceback='\n'.join(traceback)
                    )
                )

        return dict(
            status='failed with an exception',
            context='\n\n'.join(errors)
        )

    async def render_started(self, build, master):
        return dict(status='is started', context='')

    async def render_success(self, build, master):
        return dict(status='has been succeeded', context='')

    async def render_warnings(self, build, master):
        return dict(status='has been succeeded with warnings', context='')

    async def render_skipped(self, build, master):
        return dict(status='was skipped', context='')

    async def render_cancelled(self, build, master):
        return dict(status='was cancelled', context='')

    async def render_retry(self, build, master):
        return dict(status='is retried', context='')
