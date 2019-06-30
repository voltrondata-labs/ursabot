# Copyright 2019 RStudio, Inc.
# All rights reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

FROM continuumio/miniconda3

RUN conda update --all -c conda-forge && \
    conda install -c conda-forge -y \
        twisted \
        pytest \
        mock \
        flake8 \
        click \
        docker-py \
        toolz && \
    conda clean --all -y

RUN pip install --no-binary buildbot \
        buildbot \
        docker-map \
        treq \
        toposort

ADD . /ursabot
WORKDIR /ursabot

RUN pip install -e .
