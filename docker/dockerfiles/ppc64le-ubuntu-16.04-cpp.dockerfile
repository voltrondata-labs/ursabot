FROM ppc64le/ubuntu:16.04

RUN apt update -y -q && \
    apt install -y -q \
        autoconf \
        build-essential \
        cmake \
        libboost-dev \
        libboost-filesystem-dev \
        libboost-regex-dev \
        libboost-system-dev \
        python \
        python-pip \
        bison \
        flex && \
    rm -rf /var/lib/apt/lists/*

RUN pip install \
        buildbot-worker

RUN mkdir -p /buildbot
ADD /buildbot/buildbot.tac /buildbot/buildbot.tac
WORKDIR /buildbot
CMD ["twistd", "--pidfile=", "-ny", "buildbot.tac"]
