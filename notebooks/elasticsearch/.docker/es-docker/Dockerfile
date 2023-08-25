FROM docker.elastic.co/elasticsearch/elasticsearch:8.8.2

RUN bin/elasticsearch-plugin install --batch \
  "https://github.com/o19s/elasticsearch-learning-to-rank/releases/download/v1.5.8-es8.8.2/ltr-plugin-v1.5.8-es8.8.2.zip"

COPY --chown=elasticsearch:elasticsearch elasticsearch.yml /usr/share/elasticsearch/config/
RUN cat  /usr/share/elasticsearch/config/elasticsearch.yml
