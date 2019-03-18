from .client.elastic_client import ElasticClient

elastic_client = ElasticClient()
# TODO: Solr client
solrClient = None

main_client = elastic_client

def useElastic():
    global main_client
    main_client = elastic_client

def useSolr():
    global mainClient
    main_client = elastic_client
