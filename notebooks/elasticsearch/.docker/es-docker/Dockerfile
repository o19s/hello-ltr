FROM docker.elastic.co/elasticsearch/elasticsearch:7.12.1

RUN bin/elasticsearch-plugin install -b https://github.com/o19s/elasticsearch-learning-to-rank/releases/download/v1.5.5-es7.12.1/ltr-plugin-v1.5.5-es7.12.1.zip
COPY --chown=elasticsearch:elasticsearch elasticsearch.yml /usr/share/elasticsearch/config/
RUN cat  /usr/share/elasticsearch/config/elasticsearch.yml

