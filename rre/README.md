rre

This folder contains some basic RRE demonstrations for running evaluations against your LTR models.

Navigate to `solr` or `elastic` depending on which you are using and do the following:

## Getting Started
- Build the docker image: `docker build -t ltr-rre .`
- Run an evaluation: `docker run --name ltr-rre ltr-rre`
- Copy the report to your host: `docker cp ltr-rre:/rre/target/site/rre-report.xlsx .`

Alternatively, you can run thru the `evaluation` notebooks in Jupyter to run these steps for you.

__Note:__ Older versions of Docker for Linux may have issues accessing localhost on the host machine
