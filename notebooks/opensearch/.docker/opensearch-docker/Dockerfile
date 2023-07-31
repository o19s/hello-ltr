FROM opensearchproject/opensearch:2.5.0


RUN bin/opensearch-plugin install --batch \
  "https://www.github.com/opensearch-project/opensearch-learning-to-rank-base/releases/download/release-v2.1.0/ltr-plugin-v2.1.0.zip"

COPY --chown=opensearch:opensearch opensearch.yml /usr/share/opensearch/config/
RUN cat  /usr/share/opensearch/config/opensearch.yml
