FROM amd64/ubuntu:18.04

RUN apt update -y -q && \
    apt install -y -q \
        wget && \
    rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/conda/bin:$PATH
ADD install_conda.sh install_conda.sh
RUN /install_conda.sh amd64 /opt/conda
ADD conda-linux.txt conda-linux.txt
ADD conda-cpp.txt conda-cpp.txt
RUN conda install -y -q \
        --file conda-linux.txt \
        --file conda-cpp.txt \
        twisted && \
    conda clean -q --all

RUN pip install \
        buildbot-worker

RUN mkdir -p /buildbot
ADD /buildbot/buildbot.tac /buildbot/buildbot.tac
WORKDIR /buildbot
CMD ["twistd", "--pidfile=", "-ny", "buildbot.tac"]
