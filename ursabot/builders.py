# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

import copy
import toolz
import itertools
import warnings
from collections import defaultdict

from buildbot import interfaces
from buildbot.plugins import util
from codenamize import codenamize

from .docker import DockerImage
from .workers import DockerLatentWorker
from .utils import Collection, slugify


class BuildFactory(util.BuildFactory):

    def clone(self):
        return copy.deepcopy(self)

    def add_step(self, step):
        return super().addStep(step)

    def add_steps(self, steps):
        return super().addSteps(steps)

    def prepend_step(self, step):
        self.steps.insert(0, interfaces.IBuildStepFactory(step))


class Builder(util.BuilderConfig):

    # used for generating unique default names
    _ids = defaultdict(itertools.count)
    # merged with env argument
    env = None
    # concatenated to tags constructor argument
    tags = tuple()
    # default for steps argument so it gets overwritten if steps is passed
    steps = tuple()
    # prefix for name argument
    name_prefix = ''
    # merged with properties argument
    properties = None
    # merged with default_properties argument
    default_properties = None

    def __init__(self, name=None, steps=None, factory=None, workers=None,
                 tags=None, properties=None, default_properties=None, env=None,
                 **kwargs):
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

        name = name or self._generate_name()
        if self.name_prefix:
            name = f'{self.name_prefix} {name}'
        factory = factory or BuildFactory(steps)
        env = toolz.merge(self.env or {}, env or {})
        properties = toolz.merge(self.properties or {}, properties or {})
        default_properties = toolz.merge(self.default_properties or {},
                                         default_properties or {})
        workernames = None if workers is None else [w.name for w in workers]

        super().__init__(name=name, tags=tags, properties=properties,
                         defaultProperties=default_properties, env=env,
                         workernames=workernames, factory=factory, **kwargs)
        # traverse properties and defaultProperties and call any callables with
        # self as argument
        self._traverse_properties()

    @classmethod
    def _generate_name(cls, prefix=None, slug=True, ids=True, codename=None):
        name = prefix or cls.__name__
        if slug:
            name = slugify(name)
        if ids:
            name += '#{}'.format(next(cls._ids[name]))
        if codename is not None:
            # generates codename like: pushy-idea
            name += ' ({})'.format(codenamize(codename, max_item_chars=5))
        return name

    def _traverse_properties(self):
        """A small utility function to generate properties dynamically

        The builder configuration is all set up after __init__. In order to
        dynamically change values based on other values of the instance the
        base BuilderConfig class should be refactored.
        """
        def render(value):
            if callable(value):
                return value(self)
            elif isinstance(value, (list, tuple)):
                return list(map(render, value))
            elif isinstance(value, dict):
                return toolz.valmap(render, value)
            else:
                return value

        self.properties = render(self.properties)
        self.defaultProperties = render(self.defaultProperties)

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}'>"


class DockerBuilder(Builder):

    images = tuple()
    volumes = tuple()
    hostconfig = None

    def __init__(self, name=None, image=None, properties=None, tags=None,
                 hostconfig=None, volumes=tuple(), **kwargs):
        if not isinstance(image, DockerImage):
            raise ValueError('Image must be an instance of DockerImage')

        name = image.title
        tags = tags or [image.name]
        tags += list(image.platform)
        volumes = list(toolz.concat([self.volumes, volumes]))
        hostconfig = toolz.merge(self.hostconfig or {}, hostconfig or {})

        props = properties or {}
        props['docker_image'] = str(image)
        props['docker_volumes'] = volumes
        props['docker_hostconfig'] = hostconfig
        super().__init__(name=name, properties=props, tags=tags, **kwargs)

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
