#!/bin/sh

docker build . -t ltr-solr
docker-compose up
