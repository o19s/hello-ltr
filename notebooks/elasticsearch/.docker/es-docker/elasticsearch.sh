#!/bin/sh

docker run -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" elasticsearch-tlre
