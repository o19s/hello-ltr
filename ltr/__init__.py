from .client.elastic_client import ElasticClient
from .client.solr_client import SolrClient

elastic_client = ElasticClient()
solr_client = SolrClient()

main_client = elastic_client
client_mode = 'elastic'

def useElastic():
    global main_client, client_mode
    main_client = elastic_client
    client_mode = 'elastic'
    print('Switched to Elastic client_mode')

def useSolr():
    global main_client, client_mode
    main_client = solr_client
    client_mode = 'solr'
    print('Switched to Solr client_mode')
