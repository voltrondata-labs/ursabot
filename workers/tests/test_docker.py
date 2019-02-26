from textwrap import dedent

import dask
import pytest
from dockermap.api import DockerFile

from ..docker import (DockerImage, ADD, RUN, CMD, apk, apt, pip, conda,
                      arrow_images, collect)


@pytest.fixture
def testimg():
    return DockerImage('test', base='ubuntu', steps=[
        RUN(apt('python', 'python-pip')),
        ADD('requirements.txt'),
        RUN(pip('six', 'numpy', files=['requirements.txt'])),
        CMD('python')
    ])


def test_apk():
    cmd = "apk add --no-cache -q \\\n"
    tab = ' ' * 8
    assert apk('bash') == f"{cmd}{tab}bash\n"
    assert apk('bash', 'cmake') == f"{cmd}{tab}bash \\\n{tab}cmake\n"


def test_shortcuts_smoke():
    for fn in [apk, apt]:
        assert 'ninja' in fn('ninja')
        assert 'cmake' in fn('ninja', 'cmake', 'make')

    for fn in [pip, conda]:
        assert 'six' in fn('six')
        assert 'numpy' in fn('six', 'numpy', 'pandas')
        assert 'requirements.txt' in fn('six', files=['requirements.txt'])


def test_dockerfile_dsl(testimg):
    assert testimg.repo == 'test'
    assert testimg.base == 'ubuntu'

    dockerfile = str(testimg.dockerfile)
    expected = dedent("""
        FROM ubuntu

        RUN apt update -y -q && \\
            apt install -y -q \\
                python \\
                python-pip && \\
            rm -rf /var/lib/apt/lists/*

        ADD requirements.txt requirements.txt
        RUN pip install \\
                -r requirements.txt \\
                six \\
                numpy

        CMD ["python"]
    """)
    assert dockerfile.strip() == expected.strip()


def test_docker_image_save(tmp_path, testimg):
    target = tmp_path / f'{testimg.repo}.{testimg.tag}.dockerfile'
    testimg.save_dockerfile(tmp_path)
    assert target.read_text().startswith('FROM ubuntu')


def test_docker_image_build():
    pass


def test_docker_image_push():
    pass


def test_arrow_images():
    dockerfiles = [img.dockerfile for img in arrow_images]

    for df in dask.compute(*dockerfiles):
        assert isinstance(df, DockerFile)
