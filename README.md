hello-ltr

## Requirements
- An elasticsearch server running the ES LTR plugin. (See provided Dockerfile to jumpstart this process)
- A Python3 virtualenv with the requirements from requirements.txt installed
`pip install -r requirements.txt`
- A JRE to run the ranklib jar

## Dockerfile
You can use the provided Dockerfile to quickly start up an elastic instance with the LTR plugin installed

`docker build -t ltr-es .`

`docker run -d -p 9200:9200 -p 9300:9300 ltr-es`

## Overview
Once an elastic server is setup, the notebook provided by this project will:

- Index sample TMDB data
- Initialize the LTR plugin store
- Create "release" FeatureSet
- Log features for a `match_all` query
- Train two models, one that prefers old movies and another the prefers newer movies
- Submit the models to elastic for use in scoring/rescoring

The overall goal of this project is to demonstrate all of the steps required to work with LTR in elastic.  Once familiar with the process, experimentation with more advanced feature sets, queries and judgment lists is recommended.

## Getting Started
- Run `jupyter notebook` and load the hello-ltr notebook
- Run thru each cell to get more familiar with the LTR pipeline

