from ltr.client.solr_client import SolrClient
client = SolrClient()

from ltr import download
from ltr.index import rebuild
from ltr.helpers.movies import indexable_movies

corpus='http://es-learn-to-rank.labs.o19s.com/tmdb.json'
download([corpus], dest='data/');

movies=indexable_movies(movies='data/tmdb.json')
rebuild(client, index='tmdb', doc_src=movies)