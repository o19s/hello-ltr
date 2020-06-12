from ltr.helpers.movies import indexable_movies, noop

def rebuild(client, index, doc_src):
    """ Reload a configuration on disk for each search engine
        (Solr a configset, Elasticsearch a json file)
        and reindex

        """
    print("Reconfig from disk...")

    client.delete_index(index)
    client.create_index(index)

    print("Reindexing...")

    client.index_documents(index,
                           doc_src=doc_src)

    print('Done')
