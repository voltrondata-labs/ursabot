FROM ppc64le-ubuntu-18.04-cpp

ADD requirements.txt requirements.txt
RUN pip install \
        -r requirements.txt

