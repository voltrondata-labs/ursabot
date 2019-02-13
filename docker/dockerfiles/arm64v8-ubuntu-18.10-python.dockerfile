FROM arm64v8-ubuntu-18.10-cpp

ADD requirements.txt requirements.txt
RUN pip install \
        -r requirements.txt

