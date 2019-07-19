hello-ltr

The overall goal of this project is to demonstrate all of the steps required to work with LTR in Elasticsearch or Solr. Follow the setup instructions and check out the LTR notebooks in Solr or Elasticsearch

# Setup your search engine

LTR examples here for Solr or Elasticsearch which require the right search engine to be installed

## Setup Solr w/ LTR

With Docker installed, a script will launch Solr & the config under the solr/ dir in the console:

```
cd docker/solr
./launch_solr.sh
```

Or manually

- Go into the "Solr" docker directory: `cd docker/solr`
- Run `docker build . -t ltr-solr` to create a image running Solr with LTR
- Start the instance by running: `docker run --name ltr-solr -p 8983:8983 -d ltr-solr`
- Subsequently run with `docker start ltr-solr` and `docker stop ltr-solr`

## Setup Elasticsearch w/ LTR

With Docker installed, a script will launch Elasticsearch w/ Kibana tooling in the console:

```
cd docker/elasticsearch
./launch_es.sh
```

Manually build & run the containers

```
# Create Elasticsearch
cd es-docker
docker build -t ltr-elasticsearch .

# Create Kibana
cd kb-docker
docker build -t ltr-kibana .

# Launch
cd ..
docker-compose up
```

# Setup & Run Jupyter Notebook Examples

## Setup Python requirements

- Ensure Python 3 is installed on your system
- Create a virtual environment: `python3 -m venv venv`
- Start the virtual environment: `source venv/bin/activate`
- Install the requirements `pip install -r requirements.txt`

__Note:__ The above commands should be run from the root folder of the project.

## Start Jupyter notebook and confirm operation

- Run `jupyter notebook`
- Open either the "hello-ltr (Solr)" or "hello-ltr (ES)" as approriatte and ensure you get a graph at the last cell


## Getting Started
- Run `jupyter notebook` and load the hello-ltr notebook
- Run thru each cell to get more familiar with the LTR pipeline

# Docker Compose

If you hit any snags with the JDK or python dependencies, the [docker](docker/) folder has a docker-compose configuration that prepares an environment to run all of the notebooks.
