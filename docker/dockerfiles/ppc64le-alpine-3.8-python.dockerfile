FROM ppc64le-alpine-3.8-cpp

ADD requirements.txt requirements.txt
RUN pip install \
        -r requirements.txt

