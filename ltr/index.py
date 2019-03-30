import json
from ltr.helpers.movies import indexable_movies, noop

def reindex(client, schema, index='tmdb', enrich=noop):
    client.delete_index(index)
    client.create_index(index, schema)

    client.index_documents(index,
                           movie_source=indexable_movies(enrich=enrich))

def rebuild_tmdb(client, settings=None, enrich=noop):
    # Recreate the index
    if settings is None:
        with open('data/settings.json') as src:
            settings = json.load(src)

    reindex(client, schema=settings, enrich=enrich, index='tmdb')

    print('Done')
