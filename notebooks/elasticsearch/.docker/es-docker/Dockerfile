FROM docker.elastic.co/elasticsearch/elasticsearch:7.7.0

RUN bin/elasticsearch-plugin install -b http://es-learn-to-rank.labs.o19s.com/ltr-1.3.0-es7.7.0.zip 
COPY --chown=elasticsearch:elasticsearch elasticsearch.yml /usr/share/elasticsearch/config/
RUN cat  /usr/share/elasticsearch/config/elasticsearch.yml

