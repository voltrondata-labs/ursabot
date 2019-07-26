import json
import operator

import toolz
from tabulate import tabulate
from ruamel.yaml import YAML
from buildbot.util.logger import Logger
from buildbot.process.results import SUCCESS

from ursabot.formatters import MarkdownFormatter


log = Logger()


class BenchmarkCommentFormatter(MarkdownFormatter):

    def _render_table(self, jsonlines):
        """Renders the json content of a result log

        As a plaintext table embedded in a diff markdown snippet.
        """
        rows = [json.loads(line.strip()) for line in jsonlines if line]

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
            if step['results'] == SUCCESS:
                results[step['stepid']] = (line for _, line in log_lines)

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


# 2a3e076a-0cff-409a-87ab-3f3adb390ea7
class CrossbowCommentFormatter(MarkdownFormatter):

    _markdown_badge = '[![{title}]({badge})]({url})'

    badges = {
        'azure': _markdown_badge.format(
            title='Azure',
            url=(
                'https://dev.azure.com/{repo}/_build/latest'
                '?definitionId=1&branchName={branch}'
            ),
            badge=(
                'https://dev.azure.com/{repo}/_apis/build/status/'
                '{repo_dotted}?branchName={branch}'
            )
        ),
        'travis': _markdown_badge.format(
            title='TravisCI',
            url='https://travis-ci.org/{repo}/branches',
            badge='https://img.shields.io/travis/{repo}/{branch}.svg'
        ),
        'circle': _markdown_badge.format(
            title='CircleCI',
            url='https://circleci.com/gh/{repo}/tree/{branch}',
            badge=(
                'https://img.shields.io/circleci/build/github'
                '/{repo}/{branch}.svg'
            )
        ),
        'appveyor': _markdown_badge.format(
            title='Appveyor',
            url='https://ci.appveyor.com/project/{repo}/history',
            badge='https://img.shields.io/appveyor/ci/{repo}/{branch}.svg'
        )
    }

    def __init__(self, *args, crossbow_repo, azure_id=None, **kwargs):
        # TODO(kszucs): format validation
        self.crossbow_repo = crossbow_repo
        self.azure_id = azure_id
        self.yaml_parser = YAML()
        super().__init__(*args, **kwargs)

    def _render_message(self, yaml_lines):
        yaml_content = '\n'.join(yaml_lines)
        job = self.yaml_parser.load(yaml_content)

        url = 'https://github.com/{repo}/branches/all?query={branch}'
        msg = f'Submitted crossbow builds: [{{repo}} @ {{branch}}]({url})\n'
        msg += '\n|Task|Status|\n|----|------|'

        tasks = sorted(job['tasks'].items(), key=operator.itemgetter(0))
        for key, task in tasks:
            branch = task['branch']

            try:
                template = self.badges[task['ci']]
                badge = template.format(
                    repo=self.crossbow_repo,
                    repo_dotted=self.crossbow_repo.replace('/', '.'),
                    branch=branch
                )
            except KeyError:
                badge = 'unsupported CI service `{}`'.format(task['ci'])

            msg += f'\n|{key}|{badge}|'

        return msg.format(repo=self.crossbow_repo, branch=job['branch'])

    def render_success(self, build, master):
        # extract logs named as `result`
        results = {}
        for step, log_lines in self.extract_logs(build, logname='result'):
            if step['results'] == SUCCESS:
                results[step['stepid']] = (line for _, line in log_lines)

        try:
            # decode yaml objects and render the results as a github links
            # pointing to the pushed crossbow branches
            messages = toolz.valmap(self._render_message, results)
        except Exception as e:
            log.error(e)
            raise

        context = '\n\n'.join(messages.values())
        return dict(status='has been succeeded', context=context)
