from ltr.helpers.movies import indexable_movies, noop

def rebuild(client, index, doc_type, doc_src):
    """ Reload a configuration on disk for each search engine
        (Solr a configset, Elasticsearch a json file)
        and reindex

        """
    print("Reconfig from disk...")

    client.delete_index(index)
    client.create_index(index)

    print("Reindexing...")

    client.index_documents(index,
                           doc_type=doc_type,
                           doc_src=doc_src)

    print('Done')


def rebuild_tmdb(client, enrich=noop):
    movies=indexable_movies(enrich=enrich)
    rebuild(client, index='tmdb', doc_type='movie', doc_src=movies)
