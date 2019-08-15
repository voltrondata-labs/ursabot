# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.
#
# This file contains function or sections of code that are marked as being
# derivative works of Buildbot. The above license only applies to code that
# is not marked as such.

import copy
import toolz
import itertools
import warnings
from collections import defaultdict

from buildbot import interfaces, config
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Properties
from buildbot.worker.base import AbstractWorker, Worker

from .docker import DockerImage
from .workers import DockerLatentWorker
from .utils import Collection, LazyObject, instance_of, where

__all__ = ['Builder', 'DockerBuilder']


# Collection instead of list
class Builder:

    __slots__ = [
        'name',
        'workers',
        'builddir',
        'workerbuilddir',
        'env',
        'tags',
        'locks',
        'steps',
        'properties',
        'next_build',
        'next_worker',
        'can_start_build',
        'collapse_requests'
    ]
    __defaults__ = {
        'workers': [],
        'builddir': None,
        'workerbuilddir': None,
        'env': {},
        'tags': [],
        'locks': [],
        'steps': [],
        'properties': {},
        'next_build': None,
        'next_worker': None,
        'can_start_build': None,
        'collapse_requests': None
    }

    worker_filter = where()

    def __init__(self, name, **kwargs):
        self.name = name

        for k, default in self.__defaults__.items():
            classvar = getattr(self, k, default)
            argument = kwargs.get(k, default)
            # delayed initialization support with lazy objects
            # if isinstance(classvar, LazyObject):
            #     value = classvar.execute(argument)
            # else:
            #     value = argument or classvar
            setattr(self, k, argument or classvar)

        assert all(isinstance(w, AbstractWorker) for w in self.workers)

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}'>"

    def as_config(self):
        factory = BuildFactory(self.steps)

        workernames = []
        for w in self.workers:
            if isinstance(w, AbstractWorker):
                workernames.append(w.name)
            elif isinstance(w, str):
                workernames.append(w)
            else:
                config.error('`workers` must be a list of strings or '
                             'a list of worker objects')

        return BuilderConfig(
            name=self.name, workernames=workernames, factory=factory,
            description=self.__doc__, tags=self.tags, env=self.env,
            properties=self.properties, locks=self.locks,
            builddir=self.builddir, workerbuilddir=self.workerbuilddir,
            nextWorker=self.next_worker, nextBuild=self.next_build,
            collapseRequests=self.collapse_requests,
            canStartBuild=self.can_start_build
        )

    @classmethod
    def combine_with(cls, workers, name, **kwargs):
        # instantiate builders by applying Builder.worker_filter and grouping
        # the workers based on architecture or criteria
        worker_filter = instance_of(Worker) & cls.worker_filter
        suitable_workers = workers.filter(worker_filter)
        workers_by_platform = suitable_workers.groupby('platform')

        builders = []
        for platform, workers in workers_by_platform.items():
            builder = cls(name=f'{platform.title} {name}', **kwargs)
            builders.append(builder)

        return builders


class DockerBuilder(Builder):

    __slots__ = [
        *Builder.__slots__,
        'image',
        'volumes',
        'hostconfig'
    ]
    __defaults__ = {
        **Builder.__defaults__,
        'volumes': [],
        'hostconfig': {}
    }

    worker_filter = where()
    image_filter = where()

    def __init__(self, name, image, workers, **kwargs):
        self.image = image
        super().__init__(name=name, workers=workers, **kwargs)

        assert isinstance(self.image, DockerImage)
        assert all(isinstance(w, DockerLatentWorker) for w in self.workers)
        self._render_docker_properties()

    def _render_docker_properties(self):
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
            buildername=self.name,
            builddir=self.builddir,
            workerbuilddir=self.workerbuilddir,
            docker_image=str(self.image),
            docker_workdir=self.image.workdir
        )
        self.properties.update({
            'docker_image': str(self.image),
            'docker_workdir': self.image.workdir,
            'docker_volumes': props.render(self.volumes).result,
            'docker_hostconfig': props.render(self.hostconfig).result,
        })

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
        image_filter = instance_of(DockerImage) & cls.image_filter
        worker_filter = instance_of(DockerLatentWorker) & cls.worker_filter

        suitable_images = images.filter(image_filter)
        suitable_workers = workers.filter(worker_filter)

        pairs = Collection([
            (image, worker)
            for image in suitable_images
            for worker in suitable_workers
            if worker.supports(image.platform)
        ])

        builders = []
        for image, pairs in pairs.groupby(0).items():
            workers = list(toolz.pluck(1, pairs))
            if workers:
                builder_name = image.title
                if name:
                    builder_name += f' {name}'

                builder = cls(name=builder_name, image=image, workers=workers,
                              **kwargs)
                builders.append(builder)
            else:
                warnings.warn(
                    f'{cls.__name__}: there are no docker workers available '
                    f'for architecture `{image.arch}`, omitting image '
                    f'`{image}`'
                )

        return builders
