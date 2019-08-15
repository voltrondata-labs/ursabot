import pytest

from buildbot.plugins import util
from buildbot.config import ConfigErrors, BuilderConfig
from buildbot.process.factory import BuildFactory

from ursabot.builders import Builder, DockerBuilder
from ursabot.utils import Collection, Platform
from ursabot.workers import LocalWorker


def test_declarative_instantiation():
    class Declarative(Builder):
        env = {'decl': 'a'}
        tags = ['decl']
        steps = []
        properties = {'decl': 'a'}
        workers = []

    declarative = Declarative(name='declarative')
    imperative = Builder(
        name='imperative',
        env={'imp': 'b'},
        tags=['imp'],
        properties={'imp': 'b'}
    )
    hybrid = Declarative(
        name='hybrid',
        tags=['hybrid'],
        properties={'hybrid': 'c'}
    )

    assert declarative.name == 'declarative'
    assert declarative.env == {'decl': 'a'}
    assert declarative.builddir is None
    assert declarative.tags == ['decl']
    assert declarative.properties == {'decl': 'a'}
    assert declarative.workers == []
    assert declarative.steps == []

    assert imperative.name == 'imperative'
    assert imperative.env == {'imp': 'b'}
    assert imperative.builddir is None
    assert imperative.tags == ['imp']
    assert imperative.properties == {'imp': 'b'}
    assert imperative.workers == []
    assert imperative.steps == []

    assert hybrid.name == 'hybrid'
    assert hybrid.env == {'decl': 'a'}
    assert hybrid.builddir is None
    assert hybrid.tags == ['hybrid']
    assert hybrid.properties == {'hybrid': 'c'}
    assert hybrid.workers == []
    assert hybrid.steps == []


def test_docker_builder_basic():
    class Test(Builder):
        properties = {
            'A': 'a'
        }
        hostconfig = {
            'shm_size': '2G'
        }
        volumes = [
            util.Interpolate('%(prop:builddir)s:/root/.ccache:rw')
        ]

    test = Test(name='test')
    assert test.properties == {'A': 'a'}
    assert test.hostconfig == {'shm_size': '2G'}
    assert test.volumes == [
        util.Interpolate('%(prop:builddir)s:/root/.ccache:rw')
    ]


def test_builder_as_config():
    class Test(Builder):
        env = {'A': 'a'}
        tags = ['test']
        steps = []
        properties = {'A': 'a'}

    with pytest.raises(ConfigErrors):
        Test(name='test').as_config()

    platform = Platform.detect()
    workers = [
        LocalWorker('worker_a', platform=platform),
        LocalWorker('worker_b', platform=platform)
    ]
    conf = Test(name='test', workers=workers).as_config()

    assert isinstance(conf, BuilderConfig)
    assert conf.name == 'test'
    assert conf.workernames == ['worker_a', 'worker_b']
    assert conf.factory == BuildFactory([])
    assert conf.tags == ['test']
    assert conf.env == {'A': 'a'}
    assert conf.properties == {'A': 'a'}


# def test_for_workers():
#     class Test(Builder):
#         env = {'A': 'a'}
#         tags = ['test']
#         steps = []
#         properties = {'A': 'a'}
#
#     workers = Collection([
#         LocalWorker('worker_a', arch='amd64'),
#         LocalWorker('worker_b', arch='arm64v8')
#     ])
#     workers_by_arch = workers.groupby('arch')
#
#     builders = Test.for_workers(**workers_by_arch)





# def test_workers_argument():
#     workers = [
#         LocalWorker('w1'),
#         LocalWorker('w2')
#     ]
#
#     with pytest.raises(ConfigErrors):
#         A(name='a')
#     with pytest.raises(ConfigErrors):
#         A(name='a', workers=[])
#     with pytest.raises(ConfigErrors):
#         B(name='b')
#     with pytest.raises(ConfigErrors):
#         B(name='b', workers=[])
#
#     a1 = A(name='a1', workers=workers)
#     assert a1.workernames == ['w1', 'w2']
#
#     b1 = B(name='b1', workers=workers)
#     assert b1.workernames == ['w1', 'w2']
#
#     A.configure_with(workers=workers)
