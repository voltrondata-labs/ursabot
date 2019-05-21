FROM continuumio/miniconda3

RUN conda update --all -c conda-forge && \
    conda install -c conda-forge -y \
        twisted \
        pytest \
        mock \
        flake8 \
        click \
        docker-py \
        psycopg2 \
        toolz && \
    conda clean --all -y

RUN pip install --no-binary buildbot \
        buildbot-console-view \
        buildbot-grid-view \
        buildbot-waterfall-view \
        buildbot-www \
        buildbot \
        codenamize \
        docker-map \
        tabulate \
        toml \
        toposort \
        treq

ADD . /ursabot
WORKDIR /ursabot

RUN pip install -e .
