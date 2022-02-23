FROM python:3.7-stretch

# Install openjdk
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk graphviz && \
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
