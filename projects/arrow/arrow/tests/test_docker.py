# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD 2-Clause
# license that can be found in the LICENSE_BSD file.

from ursabot.docker import DockerImage, DockerFile

from ..docker import images


def test_arrow_images():
    for img in images:
        assert isinstance(img, DockerImage)
        assert isinstance(img.dockerfile, DockerFile)
