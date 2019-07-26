from ursabot.docker import DockerImage, DockerFile

from .docker import images


def test_arrow_images():
    for img in images:
        assert isinstance(img, DockerImage)
        assert isinstance(img.dockerfile, DockerFile)
