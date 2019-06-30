If you have issues getting jupyter or the JDK running on the host machine, you can use the files here to setup a docker environment with everything in one place.

## Requirements

- Docker with docker-compose
- Ports 8888/8983/9200 must be available on your host machine

## Setup

Run `docker-compose up -d` 

The above command will build all images necessary for the project and run the following services:

- Jupyter available at localhost:8888
- Solr available at localhost:8983
- Elasticsearch available at localhost:9200

## Cleanup

- To shut things down and return later run `docker-compose stop`
- To get rid of everything run `docker-compose down`
