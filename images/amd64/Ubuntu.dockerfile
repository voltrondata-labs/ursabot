FROM kszucs/buildbot-worker-amd64

USER root
RUN apt-get update -y \
 && apt-get install -y \
        autoconf \
        build-essential \
        cmake \
        libboost-dev \
        libboost-filesystem-dev \
        libboost-regex-dev \
        libboost-system-dev \
        python3 \
        python3-pip \
        bison \
        flex
USER buildbot
