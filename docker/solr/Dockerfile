FROM solr:7.7.1

USER root

ADD tmdb server/solr/configsets/tmdb
ADD msmarco server/solr/configsets/msmarco

RUN chown solr:solr server/solr/configsets/tmdb

USER solr

CMD ["solr-foreground", "-Dsolr.ltr.enabled=true"]
