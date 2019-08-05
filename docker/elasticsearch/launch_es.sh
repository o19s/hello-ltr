#!/bin/sh
cd es-docker
docker build -t ltr-elasticsearch .

cd ..
cd kb-docker
docker build -t ltr-kibana .

cd ..
docker-compose up
