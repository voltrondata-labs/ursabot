import jinja2
import toolz

from buildbot.process.results import Results


class Formatter:

    layout = None
    context = {}

    def __init__(self, layout=None, context=None):
        layout = layout or self.layout  # class' default
        if isinstance(layout, str):
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


class CommentFormatter(Formatter):

    layout = '{{ message }}'

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


class BenchmarkCommentFormatter(CommentFormatter):
    pass
