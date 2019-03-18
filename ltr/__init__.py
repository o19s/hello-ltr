from .client.elastic_client import ElasticClient

elasticClient = ElasticClient()
# TODO: Solr client
solrClient = None

mainClient = elasticClient

def useElastic():
    global mainClient
    mainClient = elasticClient

def useSolr():
    global mainClient
    mainClient = elasticClient
