hello-ltr

The overall goal of this project is to demonstrate all of the steps required to work with LTR in Elasticsearch or Solr. Follow the setup instructions and check out the LTR notebooks in Solr or Elasticsearch

# Setup your search engine

## Setup Solr w/ LTR

- Go into the "Solr" directory: `cd solr`
- Run `docker build -t ltr-solr` to create a image running Solr with LTR
- Start the instance by running: `docker run --name ltr-solr -p 8983:8983 -d ltr-solr`
- Subsequently run with `docker start ltr-solr` and `docker stop ltr-solr`

## Setup Elasticsearch w/ LTR

- Run `docker build -t ltr-es` to create a image running ES with LTR
- Start the instance by running: `docker run -d -p 9200:9200 -p 9300:9300 ltr-es`
- Subsequently run with `docker start ltr-es` and `docker stop ltr-es`

# Setup & Run Jupyter Notebook Examples

## Setup Python requirements

- Ensure Python 3 is installed on your system
- Create a virtual environment: `python3 -m venv venv`
- Start the virtual environment: `source venv/bin/activate`
- Install the requirements `pip install -r requirements.txt`

## Start Jupyter notebook and confirm operation

- Run `jupyter notebook`
- Open either the "hello-ltr (Solr)" or "hello-ltr (ES)" as approriatte and ensure you get a graph at the last cell


## Getting Started
- Run `jupyter notebook` and load the hello-ltr notebook
- Run thru each cell to get more familiar with the LTR pipeline

