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

from buildbot import interfaces
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.process.properties import Properties

from .docker import DockerImage
from .workers import DockerLatentWorker
from .utils import Collection

__all__ = ['BuildFactory', 'Builder', 'DockerBuilder']


class BuildFactory(BuildFactory):

    def clone(self):
        return copy.deepcopy(self)

    def add_step(self, step):
        return super().addStep(step)

    def add_steps(self, steps):
        return super().addSteps(steps)

    def prepend_step(self, step):
        self.steps.insert(0, interfaces.IBuildStepFactory(step))


class Builder(BuilderConfig):

    # used for generating unique default names
    _ids = defaultdict(itertools.count)
    # merged with env argument
    env = None
    # concatenated to tags constructor argument
    tags = tuple()
    # default for steps argument so it gets overwritten if steps is passed
    steps = tuple()
    # merged with properties argument
    properties = None
    # merged with default_properties argument
    default_properties = None

    def __init__(self, name, steps=None, factory=None, workers=None, tags=None,
                 properties=None, default_properties=None, env=None, **kwargs):
        if isinstance(steps, (list, tuple)):
            # replace the class' steps
            steps = steps
        elif steps is None:
            steps = self.steps
        else:
            raise TypeError('Steps must be a list')

        if isinstance(tags, (list, tuple)):
            # append to the class' tag list
            tags = filter(None, toolz.concat([self.tags, tags]))
            tags = list(toolz.unique(tags))
        elif tags is not None:
            raise TypeError('Tags must be a list')

        factory = factory or BuildFactory(steps)
        workernames = None if workers is None else [w.name for w in workers]

        env = toolz.merge(self.env or {}, env or {})
        properties = toolz.merge(self.properties or {}, properties or {})
        default_properties = toolz.merge(self.default_properties or {},
                                         default_properties or {})

        super().__init__(name=name, tags=tags, properties=properties,
                         defaultProperties=default_properties, env=env,
                         workernames=workernames, factory=factory, **kwargs)

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}'>"


class DockerBuilder(Builder):

    images = tuple()
    volumes = tuple()
    hostconfig = None

    def __init__(self, name=None, image=None, tags=None, hostconfig=None,
                 volumes=tuple(), **kwargs):
        if not isinstance(image, DockerImage):
            raise ValueError('Image must be an instance of DockerImage')

        name = image.title
        tags = tags or [image.name]
        tags += list(image.platform)
        super().__init__(name=name, tags=tags, **kwargs)

        self.image = image
        self.volumes = list(toolz.concat([self.volumes, volumes]))
        self.hostconfig = toolz.merge(self.hostconfig or {}, hostconfig or {})
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
    def builders_for(cls, workers, images=tuple(), **kwargs):
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
        if not isinstance(workers, Collection):
            workers = Collection(workers)
        if not isinstance(images, Collection):
            images = Collection(images)

        assert all(isinstance(i, DockerImage) for i in images)
        assert all(isinstance(w, DockerLatentWorker) for w in workers)

        images = images or cls.images
        workers_by_arch = workers.groupby('arch')

        builders = Collection()
        for image in images:
            if image.arch in workers_by_arch:
                workers = workers_by_arch[image.arch]
                builder = cls(image=image, workers=workers, **kwargs)
                builders.append(builder)
            else:
                warnings.warn(
                    f'{cls.__name__}: there are no docker workers available '
                    f'for architecture `{image.arch}`, omitting image '
                    f'`{image}`'
                )

        return builders
