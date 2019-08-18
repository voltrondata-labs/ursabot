from pathlib import Path

import pytest
from typing import ClassVar
from pydantic import ValidationError
from buildbot.plugins import util
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory

from ursabot.builders import Merge, Extend, Builder, DockerBuilder
from ursabot.utils import Platform
from ursabot.workers import Worker, LocalWorker, DockerLatentWorker
from ursabot.docker import DockerImage


amd64_macos = Platform(arch='amd64', distro='macos', version='10.14')
amd64_ubuntu = Platform(arch='amd64', distro='ubuntu', version='18.04')
amd64_debian = Platform(arch='amd64', distro='debian', version='10')
arm64v8_debian = Platform(arch='arm64v8', distro='debian', version='10')
arm32v7_debian = Platform(arch='arm32v7', distro='debian', version='10')

docker_host = 'unix:///var/run/docker.sock'
a = DockerLatentWorker('worker_a', password=None, docker_host=docker_host,
                       platform=amd64_macos)
b = DockerLatentWorker('worker_b', password=None, docker_host=docker_host,
                       platform=amd64_macos)
c = Worker('worker_c', password=None, platform=amd64_ubuntu)
d = Worker('worker_d', password=None, platform=amd64_debian)
e = Worker('worker_e', password=None, platform=amd64_ubuntu)
f = Worker('worker_f', password=None, platform=amd64_ubuntu)
g = Worker('worker_g', password=None, platform=arm64v8_debian)
h = Worker('worker_h', password=None, platform=amd64_macos)
i = Worker('worker_i', password=None, platform=arm64v8_debian)

docker_workers = [a, b]
plain_workers = [c, d, e, f, g, h, i]
all_workers = docker_workers + plain_workers

ubuntu_docker_image = DockerImage(
    name='ubuntu',
    base='ubuntu:18.04',
    platform=Platform(
        distro='ubuntu',
        arch='amd64',
        version='18.04'
    )
)
debian_docker_image = DockerImage(
    name='debian',
    base='debian:10',
    platform=Platform(
        distro='debian',
        arch='amd64',
        version='10'
    )
)
alpine_docker_image = DockerImage(
    name='alpine',
    base='alpine:3.10',
    platform=Platform(
        distro='alpine',
        arch='amd64',
        version='3.10'
    )
)
all_images = [ubuntu_docker_image, debian_docker_image, alpine_docker_image]


def test_declarative_instantiation():
    class Declarative(Builder):
        env = {'decl': 'a'}
        tags = ['decl']
        steps = []
        properties = {'decl': 'a'}

    with pytest.raises(ValidationError):
        Declarative()  # missing name

    declarative = Declarative(name='declarative', workers=[c, d])
    imperative = Builder(
        name='imperative',
        env={'imp': 'b'},
        tags=['imp'],
        properties={'imp': 'b'},
        workers=[e, f, g]
    )

    hybrid = Declarative(
        name='hybrid',
        tags=['hybrid'],
        properties={'hybrid': 'c'},
        workers=[c, d]
    )

    assert declarative.name == 'declarative'
    assert declarative.env == {'decl': 'a'}
    assert declarative.builddir == Path('declarative')
    assert declarative.tags == ['decl']
    assert declarative.properties == {'decl': 'a'}
    assert declarative.workers == [c, d]
    assert declarative.steps == []

    assert imperative.name == 'imperative'
    assert imperative.env == {'imp': 'b'}
    assert imperative.builddir == Path('imperative')
    assert imperative.tags == ['imp']
    assert imperative.properties == {'imp': 'b'}
    assert imperative.workers == [e, f, g]
    assert imperative.steps == []

    assert hybrid.name == 'hybrid'
    assert hybrid.env == {'decl': 'a'}
    assert hybrid.builddir == Path('hybrid')
    assert hybrid.tags == ['hybrid']
    assert hybrid.properties == {'hybrid': 'c'}
    assert hybrid.workers == [c, d]
    assert hybrid.steps == []


def test_inheritance():
    class Test(Builder):
        tags = ['a', 'b']
        env = {
            'a': 'A',
            'b': 'B'
        }
        properties = {
            'prop_a': 'A'
        }

    class TestChild(Test):
        env = {
            'c': 'C',
            'd': 'D'
        }
        properties = {
            'prop_a': 'A',
            'prop_b': 'B'
        }

    class TestMerge(TestChild):
        env = Merge(
            e='E_',
            a='A_',
            d='D_'
        )
        properties = {
            'a': 'A_',
            'b': 'B_'
        }

    class TestMergeMerge(TestMerge):
        env = Merge(
            c='C__',
            f='F__'
        )
        properties = Merge({
            'a': 'A__',
            'c': 'C__'
        })

    class TestMergeExtend(TestChild):
        tags = Extend([
            'a_',
            'b_'
        ])
        env = Merge(
            e='E_',
            a='A_',
            d='D_'
        )
        properties = {
            'a': 'A_',
            'b': 'B_'
        }

    test = Test(name='test', workers=[LocalWorker('a')])
    test_child = TestChild(name='test-child', workers=[LocalWorker('b')])
    test_merge = TestMerge(name='test-merge', workers=[LocalWorker('c')])
    test_merge_merge = TestMergeMerge(
        name='test-merge-merge',
        workers=[LocalWorker('d')]
    )
    test_merge_extend = TestMergeExtend(
        name='test-merge-Extend',
        workers=[LocalWorker('e')]
    )

    assert Test.default('tags') == test.tags == ['a', 'b']
    assert Test.default('env') == test.env == {'a': 'A', 'b': 'B'}
    assert Test.default('properties') == test.properties == {'prop_a': 'A'}

    assert TestChild.default('tags') == test_child.tags == ['a', 'b']
    assert TestChild.default('env') == test_child.env == {'c': 'C', 'd': 'D'}
    assert TestChild.default('properties') == test_child.properties == {
        'prop_a': 'A',
        'prop_b': 'B'
    }

    assert TestMerge.default('env') == Merge(e='E_', a='A_', d='D_')
    assert TestMerge.default('properties') == Merge({'a': 'A_', 'b': 'B_'})
    assert test_merge.env == {'a': 'A_', 'c': 'C', 'd': 'D_', 'e': 'E_'}
    assert test_merge.properties == {'a': 'A_', 'b': 'B_'}
    assert TestMergeMerge.default('env') == Merge(c='C__', f='F__')
    assert test_merge_merge.properties == {'a': 'A__', 'b': 'B_', 'c': 'C__'}
    assert test_merge_merge.env == {
        'a': 'A_',
        'c': 'C__',
        'd': 'D_',
        'e': 'E_',
        'f': 'F__',
    }
    assert test_merge_extend.tags == ['a', 'b', 'a_', 'b_']


def test_builddir():
    class Test(Builder):
        builddir = 'folder_a'
        workerbuilddir = 'folder_b'
        workers = [LocalWorker('a')]

    class Inherit(Test):
        workers = [LocalWorker('a'), LocalWorker('b')]

    test = Test(name='test')
    assert test.builddir == Path('folder_a')
    assert test.workerbuilddir == Path('folder_b')
    assert test.as_config().workernames == ['a']

    test = Test(name='test', builddir=Path('folder_c'))
    assert test.builddir == Path('folder_c')
    assert test.workerbuilddir == Path('folder_b')
    assert test.as_config().workernames == ['a']

    test = Test(name='test', builddir=Path('folder_c'), workerbuilddir='tmp')
    assert test.builddir == Path('folder_c')
    assert test.workerbuilddir == Path('tmp')

    inherit = Inherit(name='inherit')
    assert inherit.builddir == Path('folder_a')
    assert inherit.workerbuilddir == Path('folder_b')
    assert inherit.as_config().workernames == ['a', 'b']


def test_docker_builder_basic():
    class Basic(DockerBuilder):
        pass

    class Test(DockerBuilder):
        properties = {
            'A': 'a'
        }
        hostconfig = {
            'shm_size': '2G'
        }
        volumes = [
            util.Interpolate('%(prop:builddir)s:/root/.ccache:rw')
        ]

    builder = Basic(name='test', image=ubuntu_docker_image, workers=[a])
    assert builder.name == 'test'
    assert builder.image == ubuntu_docker_image
    assert builder.workers == [a]

    builder = Test(name='test', image=ubuntu_docker_image,
                   workers=docker_workers)
    assert builder.name == 'test'
    assert builder.image == ubuntu_docker_image
    assert builder.properties == {'A': 'a'}
    assert builder.hostconfig == {'shm_size': '2G'}
    assert builder.workers == docker_workers
    assert builder.volumes == [
        util.Interpolate('%(prop:builddir)s:/root/.ccache:rw')
    ]


def test_builder_as_config():
    class Test(Builder):
        env = {'A': 'a'}
        tags = ['test']
        steps = []
        properties = {'A': 'a'}

    with pytest.raises(ValidationError):
        Test(name='test')

    workers = [
        LocalWorker('worker_a'),
        LocalWorker('worker_b')
    ]
    conf = Test(name='test', workers=workers).as_config()

    assert isinstance(conf, BuilderConfig)
    assert conf.name == 'test'
    assert conf.workernames == ['worker_a', 'worker_b']
    assert conf.factory == BuildFactory([])
    assert conf.tags == ['test']
    assert conf.env == {'A': 'a'}
    assert conf.properties == {'A': 'a'}


def test_docker_specific_properties():
    def to_gigabytes(bytes):
        import math
        gigabytes = math.ceil(bytes / 1024**3)
        return f'{gigabytes}G'

    class Test(DockerBuilder):
        properties = {
            'A': util.Property('builddir')
        }
        hostconfig = {
            'shm_size': util.Transform(to_gigabytes, 2 * 1024**3)
        }
        volumes = [
            util.Interpolate('%(prop:builddir)s:/root/.ccache:rw')
        ]

    builder = Test(name='test', image=ubuntu_docker_image,
                   workers=docker_workers)
    config = builder.as_config()
    assert config.properties == {
        'A': 'test',
        'docker_image': str(ubuntu_docker_image),
        'docker_volumes': ['test:/root/.ccache:rw'],
        'docker_hostconfig': {'shm_size': '2G'}
    }


def test_builder_description():
    class Test(Builder):
        """Doc is the default"""

    builder = Builder(name='bldr', description='custom', workers=[c])
    assert builder.description == 'custom'

    builder = Test(name='test', workers=[c, d])
    assert builder.description == 'Doc is the default'


def test_builder_worker_filter():
    class Wrong1(Builder):
        name = 'test'
        steps = []

        @classmethod
        def worker_filter(cls, worker):
            return []

    class Wrong2(Builder):
        name = 'test'
        steps = []

        @classmethod
        def worker_filter(cls, worker):
            return None

    class Wrong3(Builder):
        name = 'test'
        steps = []

        def worker_filter(self, worker):
            return None

    class Wrong4(Builder):
        name = 'test'
        steps = []
        worker_filter = lambda worker: tuple()  # noqa

    class Good1(Builder):
        name = 'test'
        steps = []

        @classmethod
        def worker_filter(cls, worker):
            return worker

    class Good2(Builder):
        name = 'test'
        steps = []

        @staticmethod
        def worker_filter(worker):
            return worker

    class Good3(Builder):
        name = 'test'
        steps = []

        @staticmethod
        def worker_filter(worker):
            if not isinstance(worker, LocalWorker):
                raise TypeError(LocalWorker)
            else:
                return worker

    for wrong in [Wrong1, Wrong2, Wrong3, Wrong4]:
        with pytest.raises(ValidationError):
            wrong(workers=plain_workers)

    for good in [Good1, Good2]:
        workers = plain_workers
        builder = good(workers=workers)
        assert builder.workers == plain_workers

    with pytest.raises(ValidationError):
        Good3(workers=plain_workers)


def test_builder_worker_compatibilities():
    class TestBuilder(Builder):
        pass

    class TestDockeBuilder(DockerBuilder):
        pass

    with pytest.raises(ValidationError):
        TestBuilder(name='test', workers=docker_workers)
    builder = TestBuilder(name='test', workers=plain_workers)
    assert builder.workers == plain_workers

    with pytest.raises(ValidationError):
        TestDockeBuilder(name='test', image=ubuntu_docker_image,
                         workers=plain_workers)
    builder = TestDockeBuilder(name='test', image=ubuntu_docker_image,
                               workers=docker_workers)
    assert builder.workers == docker_workers


def test_builder_combine_with_unfildered_workers():
    class NoFilterBuilder(Builder):
        steps = []

    pairs = [
        ('AMD64 Macos 10.14 Test', [h]),
        ('AMD64 Ubuntu 18.04 Test', [c, e, f]),
        ('AMD64 Debian 10 Test', [d]),
        ('ARM64V8 Debian 10 Test', [g, i]),
    ]
    expected = {n: NoFilterBuilder(name=n, workers=ws) for n, ws in pairs}
    builders = NoFilterBuilder.combine_with(name='Test', workers=plain_workers)

    assert len(expected) == len(builders)
    for builder in builders:
        assert builder == expected[builder.name]


def test_builder_combine_with_only_linux_workers():
    class LinuxBuilder(Builder):
        steps = []

        @staticmethod
        def worker_filter(worker):
            try:
                if worker.platform.system != 'linux':
                    raise ValueError('Only linux workers are supported')
            except AttributeError:
                raise ValueError('Cannot determine the system of the worker')
            return worker

    pairs = [
        ('AMD64 Ubuntu 18.04 Testing', [c, e, f]),
        ('AMD64 Debian 10 Testing', [d]),
        ('ARM64V8 Debian 10 Testing', [g, i]),
    ]
    expected = {n: LinuxBuilder(name=n, workers=ws) for n, ws in pairs}
    builders = LinuxBuilder.combine_with(name='Testing', workers=all_workers)

    assert len(expected) == len(builders)
    for builder in builders:
        assert builder == expected[builder.name]


def test_builder_combine_with_darwin_workers():
    class MacosBuilder(Builder):
        platform: ClassVar[Platform] = amd64_macos

        @classmethod
        def worker_filter(cls, worker):
            if not worker.supports(cls.platform):
                raise ValueError(f'Platform `{cls.platform}` is not supported '
                                 f'by worker `{worker}`')
            return worker

    pairs = [
        ('AMD64 Macos 10.14 Test', [h])
    ]
    expected = {n: MacosBuilder(name=n, workers=ws) for n, ws in pairs}
    builders = MacosBuilder.combine_with(name='Test', workers=all_workers)

    assert len(expected) == len(builders)
    for builder in builders:
        assert builder == expected[builder.name]


def test_docker_builder_worker_and_image_filters():
    class Good(DockerBuilder):
        name = 'test'
        steps = []

        @classmethod
        def worker_filter(cls, worker):
            return worker

        @classmethod
        def image_filter(cls, image):
            return image

    builder = Good(image=ubuntu_docker_image, workers=[b, a])
    assert builder.image == ubuntu_docker_image
    assert builder.workers == [b, a]

    ubuntu_image = DockerImage(
        name='test',
        base='ubuntu:18.04',
        platform=Platform(
            distro='ubuntu',
            arch='amd64',
            version='18.04'
        )
    )
    debian_image = DockerImage(
        name='test',
        base='ubuntu:18.04',
        platform=Platform(
            distro='debian',
            arch='amd64',
            version='10'
        )
    )
    darwin_worker = LocalWorker(
        'test-worker-darwin',
        platform=Platform(
            arch='amd64',
            system='darwin',
            distro='macos',
            version='10.14.6'
        )
    )
    linux_docker_worker = DockerLatentWorker(
        'test-worker-linux-docker',
        password=None,
        docker_host='unix:///var/run/docker.sock',
        platform=Platform(
            arch='amd64',
            system='linux',
            distro=None,
            version=None
        )
    )

    class UbuntuDockerOnLinuxHost(DockerBuilder):
        name = 'test'
        steps = []

        @classmethod
        def worker_filter(cls, worker):
            if worker.platform.system != 'linux':
                raise ValueError('Only linux docker workers are supported')
            return worker

        @classmethod
        def image_filter(cls, image):
            if image.platform.distro != 'ubuntu':
                raise ValueError('Only ubuntu images are supported')
            return image

    bldr = UbuntuDockerOnLinuxHost(
        image=ubuntu_image,
        workers=[linux_docker_worker]
    )
    assert bldr.image == ubuntu_image
    assert bldr.workers == [linux_docker_worker]

    with pytest.raises(ValidationError):
        UbuntuDockerOnLinuxHost(
            image=debian_image,
            workers=[linux_docker_worker]
        )
    with pytest.raises(ValidationError):
        UbuntuDockerOnLinuxHost(
            image=ubuntu_image,
            workers=[darwin_worker]
        )
    with pytest.raises(ValidationError):
        UbuntuDockerOnLinuxHost(
            image=ubuntu_image,
            workers=[linux_docker_worker, darwin_worker]
        )


def test_docker_builder_combine_with_workers_and_images():
    class Test(DockerBuilder):
        pass

    builders = Test.combine_with(workers=all_workers, images=all_images)
    expected = {
        'Ubuntu': Test(
            name='Ubuntu',
            image=ubuntu_docker_image,
            workers=docker_workers
        ),
        'Debian': Test(
            name='Debian',
            image=debian_docker_image,
            workers=docker_workers
        ),
        'Alpine': Test(
            name='Alpine',
            image=alpine_docker_image,
            workers=docker_workers
        )
    }
    assert len(builders) == len(expected)
    for builder in builders:
        assert builder == expected[builder.name]

    class TestApt(DockerBuilder):

        @classmethod
        def image_filter(cls, image):
            if image.platform.distro not in {'debian', 'ubuntu'}:
                raise ValueError("Image doesn't have `apt` command")
            return image

    builders = TestApt.combine_with(workers=all_workers, images=all_images)
    expected = {
        'Ubuntu': Test(
            name='Ubuntu',
            image=ubuntu_docker_image,
            workers=docker_workers
        ),
        'Debian': Test(
            name='Debian',
            image=debian_docker_image,
            workers=docker_workers
        )
    }
    assert len(builders) == len(expected)
    for builder in builders:
        assert builder == expected[builder.name]
