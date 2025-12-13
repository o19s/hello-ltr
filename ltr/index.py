def rebuild(client, index, doc_src, force = False):
    """ Reload a configuration on disk for each search engine
        (Solr a configset, Elasticsearch a json file)
        and reindex
    """

    if client.check_index_exists(index):
        if (force):
            client.delete_index(index)
            client.create_index(index)
            client.index_documents(index, doc_src=doc_src)
        else:
            print(f"Index {index} already exists. Use `force = True` to delete and recreate")
            return None
    else:
        client.create_index(index)
        client.index_documents(index, doc_src=doc_src)
