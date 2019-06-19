import json as jsonmodule
import toolz

from buildbot.util import toJson
from buildbot.util.logger import Logger
from buildbot.test.fake.httpclientservice import (
    HTTPClientService, ResponseWrapper)

from ursabot.utils import GithubClientService as OriginalGithubClientService
from ursabot.utils import ensure_deferred


log = Logger()


def pick(whitelist, d):
    return toolz.keyfilter(lambda k: k in whitelist, d)


# XXX: it must be named same as the original one because of some dark magic
# used for the service identification
class GithubClientService(HTTPClientService):

    def __init__(self, base_url, tokens, **kwargs):
        super().__init__(base_url, **kwargs)
        self._tokens = tokens

    @classmethod
    def getFakeService(cls, master, case, *args, **kwargs):
        ret = cls.getService(master, *args, **kwargs)

        def assertNotCalled(self, *_args, **_kwargs):
            case.fail('GithubClientService called with *{!r}, **{!r} '
                      'while should be called *{!r} **{!r}'
                      .format(_args, _kwargs, args, kwargs))

        case.patch(OriginalGithubClientService, '__init__', assertNotCalled)

        @ret.addCallback
        def assertNoOutstanding(fake):
            fake.case = case
            case.addCleanup(fake.assertNoOutstanding)
            return fake

        return ret

    def expect(self, method, ep, params=None, data=None, json=None, code=200,
               content=None, content_json=None, headers=None):
        if content is not None and content_json is not None:
            return ValueError('content and content_json cannot be both '
                              'specified')

        if content_json is not None:
            content = jsonmodule.dumps(content_json, default=toJson)

        self._expected.append(
            dict(method=method, ep=ep, params=params, data=data, json=json,
                 code=code, content=content, headers=headers)
        )

    @ensure_deferred
    async def _doRequest(self, method, ep, params=None, data=None, json=None,
                         headers=None):
        assert ep == '' or ep.startswith('/'), 'ep should start with /: ' + ep
        if not self.quiet:
            log.debug('{method} {ep} {params!r} <- {data!r}',
                      method=method, ep=ep, params=params, data=data or json)

        if json is not None:
            # ensure that the json is really jsonable
            jsonmodule.dumps(json, default=toJson)
        if not self._expected:
            raise AssertionError(
                'Not expecting a request, while we got: '
                'method={!r}, ep={!r}, params={!r}, data={!r}, json={!r}'
                .format(method, ep, params, data, json)
            )
        expect = self._expected.pop(0)

        kwargs = dict(method=method, ep=ep, params=params, data=data,
                      json=json, headers=headers)
        expected = pick(kwargs.keys(), expect)

        signature = ('method={method}, ep={ep}, params={params}, data={data}, '
                     'json={json}, headers={headers}')
        if expected != kwargs:
            expecting = signature.format(**expected)
            got = signature.format(**kwargs)
            raise AssertionError(f'\nExpecting:\n{expecting}\nGot:\n{got}')

        if not self.quiet:
            log.debug('{method} {ep} -> {code} {content!r}',
                      method=method, ep=ep, code=expect['code'],
                      content=expect['content'])

        return ResponseWrapper(expect['code'], expect['content'])
