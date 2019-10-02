# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import toolz
import warnings
import operator
from pathlib import Path
from typing import Union, List, Dict, Callable, Optional

from buildbot.plugins import util, steps
from buildbot.util import safeTranslate, bytes2unicode
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Properties
from buildbot.worker.base import AbstractWorker, Worker

from .docker import DockerImage
from .workers import DockerLatentWorker
from .utils import Annotable, InstanceOf

__all__ = ['Builder', 'DockerBuilder']


Step = steps.BuildStep
Lock = Union[util.MasterLock, util.WorkerLock]
Renderable = Union[util.Property, util.Interpolate, util.Transform, str]
ImageFilter = Callable[[DockerImage], bool]
WorkerFilter = Callable[[AbstractWorker], bool]


class Builder(Annotable):
    name: str
    workers: List[Worker]
    builddir: Optional[Union[Path, str]] = None
    workerbuilddir: Optional[Union[Path, str]] = None
    description: str = ''
    env: Dict[str, Renderable] = {}
    tags: List[str] = []
    locks: List[Lock] = []
    steps: List[Step] = []
    properties: Dict[str, Renderable] = {}
    next_build: Optional[Callable] = None
    next_worker: Optional[Callable] = None
    can_start_build: Optional[Callable] = None
    collapse_requests: Optional[Callable] = None
    worker_filter: Optional[WorkerFilter] = lambda w: True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        default_builddir = Path(bytes2unicode(safeTranslate(self.name)))
        self.builddir = Path(self.builddir or default_builddir)
        self.workerbuilddir = Path(self.workerbuilddir or default_builddir)
        self.description = self.description or self.__doc__

        for worker in self.workers:
            if not self.worker_filter(worker):
                raise ValueError(f'Worker `{worker}` is not suitable for '
                                 f'builder `{self}`')

    def _render_properties(self):
        props = Properties(
            buildername=self.name,
            builddir=str(self.builddir),
            workerbuilddir=str(self.workerbuilddir)
        )
        rendered = props.render(
            self.properties
        )
        return rendered.result

    def as_config(self):
        factory = BuildFactory(self.steps)
        properties = self._render_properties()
        workernames = [w.name for w in self.workers]
        return BuilderConfig(
            name=self.name, workernames=workernames, factory=factory,
            properties=properties, description=self.__doc__,
            tags=self.tags, env=self.env, locks=self.locks,
            builddir=str(self.builddir),
            workerbuilddir=str(self.workerbuilddir),
            nextWorker=self.next_worker, nextBuild=self.next_build,
            collapseRequests=self.collapse_requests,
            canStartBuild=self.can_start_build
        )

    @classmethod
    def combine_with(cls, workers, name=None, **kwargs):
        # instantiate builders by applying Builder.worker_filter and grouping
        # the workers based on architecture or criteria
        suitable_workers = filter(InstanceOf(Worker), workers)
        suitable_workers = filter(cls.worker_filter, suitable_workers)

        name = name or cls.__name__

        workers_by_platform = toolz.groupby(
            operator.attrgetter('platform'),
            suitable_workers
        )

        builders = []
        for platform, workers in workers_by_platform.items():
            name_ = f'{platform.title()} {name}'.strip()
            builder = cls(name=name_, workers=workers, **kwargs)
            builders.append(builder)

        return builders


class DockerBuilder(Builder):

    image: DockerImage
    workers: List[DockerLatentWorker]
    volumes: List[Renderable] = []
    hostconfig: Dict[str, Renderable] = {}
    image_filter: Optional[ImageFilter] = lambda i: True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not self.image_filter(self.image):
            raise ValueError(f'Image `{self.image}` is not sutable for '
                             f'builder `{self}`')

        for worker in self.workers:
            if not worker.supports(self.image.platform):
                raise ValueError(f"Worker {worker} doesn't support the "
                                 f"image's platform {self.image.platform}")

    def _render_properties(self):
        """Render docker properties dinamically.

        Docker specific configuration defined in the DockerBuilder instances
        are passed as properties to the DockerLatentWorker.
        Only scalar properies are allowed in BuilderConfig instances, so
        defining docker volumes referring the builddir would require
        boilerplate and deeper understanding how the build properties are
        propegated through the buildbot objects.
        So using traditional property interpolation with properties like the
        docker image's workdir, builddir, or the buildername makes the volume
        definition easier.

        Note that the builddir and workerbuilddir variables of the builder
        config are different from the ones we see on the buildbot ui under
        the properties tab.

        License note:
           The property descriptions below are copied from the buildbot docs.

        self.builddir:
           Specifies the name of a subdirectory of the master’s basedir in
           which everything related to this builder will be stored. This
           holds build status information. If not set, this parameter
           defaults to the builder name, with some characters escaped. Each
           builder must have a unique build directory.
        self.workerbuilddir:
           Specifies the name of a subdirectory (under the worker’s
           configured base directory) in which everything related to this
           builder will be placed on the worker. This is where checkouts,
           compiles, and tests are run. If not set, defaults to builddir.
           If a worker is connected to multiple builders that share the same
           workerbuilddir, make sure the worker is set to run one build at a
           time or ensure this is fine to run multiple builds from the same
           directory simultaneously.
        """
        props = Properties(
            buildername=str(self.name),
            builddir=str(self.builddir),
            workerbuilddir=str(self.workerbuilddir),
            docker_image=str(self.image),
            docker_workdir=self.image.workdir,
        )
        rendered = props.render({
            **self.properties,
            'docker_image': str(self.image),
            'docker_workdir': self.image.workdir,
            'docker_volumes': self.volumes,
            'docker_hostconfig': self.hostconfig
        })
        return rendered.result

    @classmethod
    def combine_with(cls, workers, images, name=None, **kwargs):
        """Instantiates builders based on the available workers

        The workers and images are matched based on their architecture.

        Parameters
        ----------
        workers : List[DockerLatentWorker]
            Worker instances the builders may run on.
        images : List[DockerImage], default []
            Docker images the builder's steps may run in.
            Pass None to use class' images property.

        Returns
        -------
        docker_builder : List[DockerBuilder]
            Builder instances.
        """
        suitable_images = filter(InstanceOf(DockerImage), images)
        suitable_images = filter(cls.image_filter, suitable_images)

        suitable_workers = filter(InstanceOf(DockerLatentWorker), workers)
        suitable_workers = filter(cls.worker_filter, suitable_workers)
        suitable_workers = list(suitable_workers)

        # join the images with the suitable workers
        image_worker_pairs = [
            (image, worker)
            for image in suitable_images
            for worker in suitable_workers
            if worker.supports(image.platform)
        ]

        # group the suitable workers for each image
        pairs_by_image = toolz.groupby(0, image_worker_pairs).items()
        workers_by_image = {
            image: list(toolz.pluck(1, pairs))
            for image, pairs in pairs_by_image
        }

        builders = []
        for image, workers in workers_by_image.items():
            if workers:
                builder_name = image.title or image.name.title()
                if name:
                    builder_name += f' {name}'

                builder = cls(name=builder_name, image=image, workers=workers,
                              **kwargs)
                builders.append(builder)
            else:
                warnings.warn(
                    f'{cls.__name__}: there are no docker workers available '
                    f'for platform `{image.platform}`, omitting image '
                    f'`{image}`'
                )

        return builders
