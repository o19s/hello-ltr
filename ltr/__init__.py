from .client.elastic_client import ElasticClient
from .client.solr_client import SolrClient

elastic_client = ElasticClient()
# TODO: Solr client
solr_client = SolrClient()

main_client = elastic_client

def useElastic():
    global main_client
    main_client = elastic_client
    print('Switched to Elastic mode')

def useSolr():
    global main_client
    main_client = solr_client
    print('Switched to Solr mode')
