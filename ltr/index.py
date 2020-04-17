from ltr.helpers.movies import indexable_movies, noop

def rebuild(client, index, doc_type, doc_src, force=False):
    """ Reload a configuration on disk for each search engine
        (Solr a configset, Elasticsearch a json file)
        and reindex

        """
    
    if (client.check_index_exists):
        if (force):
            client.delete_index(index)
            client.create_index(index)
            client.index_documents(index,
                                   doc_type=doc_type,
                                   doc_src=doc_src)
        else:
            print("Index {} already exists. Use `force = True` to delete and recreate".format(index))
            return None
    else:
        client.delete_index(index)
        client.create_index(index)
        client.index_documents(index,
                               doc_type=doc_type,
                               doc_src=doc_src)
            
    print('Done')


def rebuild_tmdb(client, enrich=noop, force=False):
    movies=indexable_movies(enrich=enrich)
    rebuild(client, index='tmdb', doc_type='movie', doc_src=movies, force = force)
