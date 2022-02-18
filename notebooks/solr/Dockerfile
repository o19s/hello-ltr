FROM solr:8.11.1

USER root

ADD tmdb/solr_config /var/solr/data/configsets/tmdb
RUN chown solr:solr /var/solr/data/configsets/tmdb

ADD msmarco/solr_config /var/solr/data/configsets/msmarco
RUN chown solr:solr /var/solr/data/configsets/msmarco

USER solr

CMD ["solr-foreground", "-Dsolr.ltr.enabled=true"]
