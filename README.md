hello-ltr

The overall goal of this project is to demonstrate all of the steps required to work with LTR in Elasticsearch or Solr. Follow the setup instructions and check out the LTR notebooks in Solr or Elasticsearch

# Setup your search engine

LTR examples here for Solr or Elasticsearch which require the right search engine to be installed

## Setup Solr w/ LTR

With Docker installed, a script will launch Solr along with each collection's config in the console:

```
cd docker/solr
docker-compose up
```

## Setup Elasticsearch w/ LTR

With Docker installed, a script will launch Elasticsearch w/ Kibana tooling in the console:

```
cd docker/elasticsearch
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
- Browse to notebooks/{search\_engine}/{collection} 
- Open either the "hello-ltr (Solr)" or "hello-ltr (ES)" as appropriate and ensure you get a graph at the last cell


## Getting Started
- Run `jupyter notebook` and load the hello-ltr notebook
- Run thru each cell to get more familiar with the LTR pipeline
