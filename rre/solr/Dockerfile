FROM maven:3.6.0-jdk-8

# Clone the RRE repo
RUN git clone https://github.com/SeaseLtd/rated-ranking-evaluator
WORKDIR rated-ranking-evaluator

# Build RRE
RUN mvn clean install

# Bring over the RRE config
WORKDIR /
COPY . rre
WORKDIR rre

# By default, run an RRE evaluation if no other command is specified
CMD mvn clean install
