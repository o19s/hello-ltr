FROM python:3.9.17-slim-bookworm

# Get openjdk
ENV JAVA_HOME=/opt/java/openjdk
COPY --from=eclipse-temurin:11 $JAVA_HOME $JAVA_HOME
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Install graphviz
RUN apt-get update && \
    apt-get install -y graphviz && \
    apt-get clean;

# Setup a user
RUN useradd -ms /bin/bash ltr
WORKDIR /home/ltr

# Make current directory accesible
ADD . /home/ltr/hello-ltr

# Install requirements
RUN chown -R ltr.ltr hello-ltr
WORKDIR /home/ltr/hello-ltr

RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install -r requirements.txt
USER ltr

CMD jupyter notebook --ip=0.0.0.0 --no-browser --NotebookApp.token=''
