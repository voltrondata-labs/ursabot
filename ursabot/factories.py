from buildbot.plugins import util

from .steps import checkout, ls, mkdir, cmake, compile, test, echo


factory = util.BuildFactory()
factory.addStep(checkout)
factory.addStep(ls)
factory.addStep(mkdir)
factory.addStep(cmake)
factory.addStep(compile)
factory.addStep(test)


echo_factory = util.BuildFactory()
echo_factory.addStep(checkout)
echo_factory.addStep(ls)
echo_factory.addStep(echo)
