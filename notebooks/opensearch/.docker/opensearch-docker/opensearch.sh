#!/bin/sh

docker run -p 9301:9301 -p 9400:9400 -e "discovery.type=single-node" opensearch-tlre
