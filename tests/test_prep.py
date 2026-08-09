"""
Test preparation script for downloading and indexing test data.

This script prepares the test environment by:
- Downloading the TMDB corpus from the remote URL
- Converting movies to indexable format
- Rebuilding the Solr index with test data

Note: This is a utility script, not a test file. It's used to prepare
test data before running tests.
"""

from ltr import download
from ltr.helpers.movies import indexable_movies
from ltr.index import rebuild
from tests.client_factory import create_solr_client

client = create_solr_client()

corpus = "http://es-learn-to-rank.labs.o19s.com/tmdb.json"
download([corpus], dest="data/")

movies = indexable_movies(movies_path="data/tmdb.json")
rebuild(client, index="tmdb", doc_src=movies)
