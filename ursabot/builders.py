# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.
#
# This file contains function or sections of code that are marked as being
# derivative works of Buildbot. The above license only applies to code that
# is not marked as such.

import toolz
import warnings
import operator
from pathlib import Path
from typing import Union, List, Dict, Callable, ClassVar

from pydantic import BaseModel, validator
from buildbot.plugins import util, steps
from buildbot.util import safeTranslate, bytes2unicode
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Properties
from buildbot.worker.base import AbstractWorker, Worker

from .docker import DockerImage
from .workers import DockerLatentWorker
from .utils import filter_except, filter_instances

__all__ = ['Builder', 'DockerBuilder']


Step = steps.BuildStep
Lock = Union[util.MasterLock, util.WorkerLock]
Renderable = Union[util.Property, util.Interpolate, util.Transform, str]
ImageFilter = Callable[[DockerImage], bool]
WorkerFilter = Callable[[AbstractWorker], bool]


class Marker:
    pass


class Merge(Marker, dict):
    pass


class Extend(Marker, list):
    pass


class Builder(BaseModel):

    class Config:
        arbitrary_types_allowed = True

    name: str
    workers: List[Worker]
    builddir: Path = None
    workerbuilddir: Path = None
    description: str = ''
    env: Dict[str, Renderable] = {}
    tags: List[str] = []
    locks: List[Lock] = []
    steps: List[Step] = []
    properties: Dict[str, Renderable] = {}
    next_build: Callable = None
    next_worker: Callable = None
    can_start_build: Callable = None
    collapse_requests: Callable = None
    worker_filter: ClassVar[WorkerFilter] = lambda w: True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate()

    def _validate(self):
        pass

    @classmethod
    def default(cls, field_name):
        """Returns the default value of a field"""
        return cls.__fields__[field_name].default

    @classmethod
    def _traverse_defaults(cls, field_name, field_value, marker_type):
        values = [field_value]
        for base in cls.__mro__[1:]:
            if not isinstance(field_value, marker_type):
                break
            field_value = base.default(field_name)
            values.append(field_value)
        values.reverse()
        return values

    @validator('builddir', 'workerbuilddir', pre=True, always=True)
    def _default_builddir(cls, v, values):
        default = bytes2unicode(safeTranslate(values.get('name', '')))
        return v or Path(default)

    @validator('description', pre=True, always=True)
    def _default_description(cls, v):
        return cls.__doc__ if not v and cls.__doc__ else v

    @validator('env', 'properties', pre=True, always=True, whole=True)
    def _merge_if_marked(cls, v, values, field):
        vs = cls._traverse_defaults(field.name, v, Merge)
        return toolz.merge(vs)

    @validator('tags', 'locks', 'steps', pre=True, always=True, whole=True)
    def _extend_if_marked(cls, v, values, field):
        vs = cls._traverse_defaults(field.name, v, Extend)
        return list(toolz.concat(vs))

    @validator('workers', pre=True, always=True)
    def _is_worker_suitable(cls, worker):
        if not cls.worker_filter(worker):
            raise ValueError(f'Worker `{worker}` is not sutable for '
                             f'builder `{cls}`')
        return worker

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
            builddir=self.builddir, workerbuilddir=self.workerbuilddir,
            nextWorker=self.next_worker, nextBuild=self.next_build,
            collapseRequests=self.collapse_requests,
            canStartBuild=self.can_start_build
        )

    @classmethod
    def combine_with(cls, workers, name, **kwargs):
        # instantiate builders by applying Builder.worker_filter and grouping
        # the workers based on architecture or criteria
        suitable_workers = filter_instances(Worker, workers)
        suitable_workers = filter_except(cls._is_worker_suitable, workers)

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
    image_filter: ClassVar[ImageFilter] = lambda i: True

    @validator('image', pre=True, always=True)
    def _is_image_suitable(cls, image):
        if not cls.image_filter(image):
            raise ValueError(f'Image `{image}` is not sutable for '
                             f'builder `{cls}`')
        return image

    def _validate(self):
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
            workerbuilddir=str(self.workerbuilddir)
        )
        rendered = props.render({
            **self.properties,
            'docker_image': str(self.image),
            # 'docker_workdir': self.image.workdir,
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
        suitable_images = filter_instances(DockerImage, images)
        suitable_images = filter_except(cls._is_image_suitable,
                                        suitable_images)

        suitable_workers = filter_instances(DockerLatentWorker, workers)
        suitable_workers = filter_except(cls._is_worker_suitable,
                                         suitable_workers)
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
