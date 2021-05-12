# Hello LTR :)

The overall goal of this project is to demonstrate all of the steps required to work with LTR in Elasticsearch or Solr. There's two modes of running. Just running and editing notebooks in a docker container. Or local development (also requiring docker to run the search engine).

## No fuss setup: You just want to play with LTR

Follow these steps if you're just playing around & are OK with possibly losing some work (all notebooks exist just in the docker container)

With docker & docker-compose simply run

```
docker-compose up
```

at the root dir and go to town!

This will run jupyter and all search engines in Docker containers. Check that each is up at the default ports:

- Solr: [localhost:8983](localhost:8983)
- Elasticsearch: [localhost:9200](localhost:9200)
- Kibana: [localhost:5601](localhost:5601)
- Jupyter: [localhost:8888](localhost:8888)

## You want to build your own LTR notebooks

Follow these steps if you want to do more serious work with the notebooks. For example, if you want to build a demo with your work's data or something you want to preserve later.

### Run your search engine with Docker

You probably just want to work with one search engine. So whichever one you're working with, launch that search engine in Docker.

#### Running Solr w/ LTR

Setup Solr with docker compose to work with just Solr examples:

```
cd notebooks/solr
docker-compose up
```

#### Running Elasticsearch w/ LTR

Setup Elasticsearch with docker compose to work with just Elasticsearch examples:

```
cd notebooks/elasticsearch
docker-compose up
```

### Run Jupyter locally w/ Python 3 and all prereqs

#### Setup Python requirements

- Ensure Python 3 is installed on your system
- Create a virtual environment: `python3 -m venv venv`
- Start the virtual environment: `source venv/bin/activate`
- Check install tooling is up to date `python -m pip install -U pip wheel setuptools`
- Install the requirements `pip install -r requirements.txt`

__Note:__ The above commands should be run from the root folder of the project.

#### Start Jupyter notebook and confirm operation

- Run `jupyter notebook`
- Browse to notebooks/{search\_engine}/{collection} 
- Open either the "hello-ltr (Solr)" or "hello-ltr (ES)" as appropriate and ensure you get a graph at the last cell

## Tests

### Automatically run everything...

To run a full suite of tests, such as to verify a PR, you can simply run

./tests/test.sh

Optionally with containers rebuilt

./tests/test.sh --rebuild-containers

Failing tests will have their output in `tests/last_run.ipynb`

### While developing...

For more informal development:

- Startup the Solr and ES Docker containers
- Do your development
- Run the command as needed:
`python tests/run_most_nbs.py`
- Tests fail if notebooks return any errors
  - The failing notebook will be stored at `tests/last_run.ipynb`
