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

import os
from pathlib import Path

from twisted.application import service
from twisted.python.logfile import LogFile
from twisted.python.log import ILogObserver, FileLogObserver

from buildbot.master import BuildMaster
from ursabot.configs import BuildmasterConfigLoader

# TODO(factor out this boilerplate to the configs.py)

# Default umask for server
umask = None
rotateLength = 10000000
maxRotatedFiles = 10
basedir = Path().parent.absolute()
configfile = basedir / 'master.cfg'

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')
logfile = LogFile.fromFullPath(
    str(basedir / 'twistd.log'),
    rotateLength=rotateLength,
    maxRotatedFiles=maxRotatedFiles
)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

loader = BuildmasterConfigLoader(configfile, variable='master')
master = BuildMaster(str(basedir), umask=umask, config_loader=loader)
master.setServiceParent(application)
master.log_rotation.rotateLength = rotateLength
master.log_rotation.maxRotatedFiles = maxRotatedFiles
