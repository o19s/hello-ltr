import json

def reindex(client, schema, movieDict={}, index='tmdb'):
    client.delete_index(index)
    client.create_index(index, schema)
    client.index_documents(index, movieDict)

def rebuild_tmdb(client, settings=None):
    # Recreate the index
    if settings is None:
        with open('data/settings.json') as src:
            settings = json.load(src)

    reindex(client, movieDict=json.load(open('data/tmdb.json')), schema=settings, index='tmdb')

    print('Done')
