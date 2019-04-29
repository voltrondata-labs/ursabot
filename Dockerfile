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
