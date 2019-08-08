# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import jinja2
from buildbot.plugins import util

__all__ = ['GithubAuth', 'Authz']


class GithubAuth(util.GitHubAuth):

    def __getstate__(self):
        # jinja2.Template is not deepcopy-able
        return {k: v for k, v in self.__dict__.items()
                if k != 'getUserTeamsGraphqlTplC'}

    def __setstate__(self, dct):
        self.__dict__ = dct
        if self.getTeamsMembership:
            self.getUserTeamsGraphqlTplC = jinja2.Template(
                self.getUserTeamsGraphqlTpl.strip()
            )


# just for convenience
Authz = util.Authz
