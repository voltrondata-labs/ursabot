from .steps import checkout, ls, mkdir, cmake, compile, test, echo, conda_init
from .utils import BuildFactory


cpp = BuildFactory([
    checkout,
    ls,
    mkdir,
    cmake,
    compile,
    test
])

conda_cpp = cpp.clone()
conda_cpp.prepend_step(conda_init)

echo_factory = BuildFactory()
echo_factory.add_step(checkout)
echo_factory.add_step(ls)
echo_factory.add_step(echo)
