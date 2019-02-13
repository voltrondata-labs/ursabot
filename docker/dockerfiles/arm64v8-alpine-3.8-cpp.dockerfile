FROM arm64v8/alpine:3.8

RUN apk add --no-cache -q \
        autoconf \
        bash \
        bison \
        boost-dev \
        cmake \
        flex \
        g++ \
        gcc \
        git \
        gzip \
        make \
        musl-dev \
        ninja \
        wget \
        zlib-dev \
        python-dev

RUN python -m ensurepip
RUN pip install \
        buildbot-worker

RUN mkdir -p /buildbot
ADD /buildbot/buildbot.tac /buildbot/buildbot.tac
WORKDIR /buildbot
CMD ["twistd", "--pidfile=", "-ny", "buildbot.tac"]
