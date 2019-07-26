import toolz


class ProjectConfig:

    def __init__(self, workers, builders, schedulers, pollers=None,
                 reporters=None):
        self.workers = workers
        self.builders = builders
        self.schedulers = schedulers
        self.pollers = pollers or []
        self.reporters = reporters or []


def MasterConfig(title, url, webui_port, worker_port, database_url, projects,
                 auth=None, authz=None, change_hook=None,
                 secret_providers=None):
    """Returns with the dictionary that the buildmaster pays attention to."""

    def component(key):
        return list(toolz.concat(getattr(p, key) for p in projects))

    if change_hook is None:
        hook_dialect_config = {}
    else:
        hook_dialect_config = change_hook._as_hook_dialect_config()

    return {
        'buildbotNetUsageData': None,
        'title': title,
        'titleURL': url,
        'buildbotURL': url,
        'workers': component('workers'),
        'builders': component('builders'),
        'schedulers': component('schedulers'),
        'services': component('reporters'),
        'change_source': component('pollers'),
        'secretsProviders': secret_providers,
        'protocols': {'pb': {'port': worker_port}},
        'db': {'db_url': 'sqlite:///ursabot.sqlite'},
        'www': {
            'port': webui_port,
            'auth': auth,
            'authz': authz,
            'change_hook_dialects': hook_dialect_config,
            'plugins': {
                'waterfall_view': {},
                'console_view': {},
                'grid_view': {}
            }
        }
    }
    # c['www']['change_hook_dialects']['github'] = {
    #     'class': UrsabotHook,
    #     'secret': util.Interpolate(conf.hooks.github.secret),
    #     'token': [
    #         util.Interpolate(token) for token in conf.hooks.github.tokens
    #     ],
    #     'debug': conf.hooks.github.debug,
    #     'strict': True,
    #     'verify': True
    # }
