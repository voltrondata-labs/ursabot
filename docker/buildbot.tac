# This file is mostly a derivative work of Buildbot.
#
# Buildbot is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import fnmatch
import os
import sys

from twisted.application import service
from twisted.python.log import FileLogObserver
from twisted.python.log import ILogObserver

from buildbot_worker.bot import Worker

# setup worker
basedir = os.path.abspath(os.path.dirname(__file__))
application = service.Application("buildbot-worker")


application.setComponent(ILogObserver, FileLogObserver(sys.stdout).emit)
# and worker on the same process!
buildmaster_host = os.environ.get("BUILDMASTER", "localhost")
port = int(os.environ.get("BUILDMASTER_PORT", 9989))
workername = os.environ.get("WORKERNAME", "docker")
passwd = os.environ.get("WORKERPASS")

# delete the password from the environ so that it is not leaked in the log
blacklist = os.environ.get("WORKER_ENVIRONMENT_BLACKLIST", "WORKERPASS").split()
for name in list(os.environ.keys()):
    for toremove in blacklist:
        if fnmatch.fnmatch(name, toremove):
            del os.environ[name]

keepalive = 600
umask = None
maxdelay = 300
allow_shutdown = None
maxretries = 10

s = Worker(
    buildmaster_host,
    port,
    workername,
    passwd,
    basedir,
    keepalive,
    umask=umask,
    maxdelay=maxdelay,
    allow_shutdown=allow_shutdown,
    maxRetries=maxretries,
)
s.setServiceParent(application)
