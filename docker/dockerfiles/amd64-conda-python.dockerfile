FROM amd64-conda-cpp

ADD conda-python.txt conda-python.txt
RUN conda install -y -q \
        --file conda-python.txt && \
    conda clean -q --all

