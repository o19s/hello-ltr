from ltr import mainClient
import json

def reindex(schema, movieDict={}, index='tmdb'):
    mainClient.delete_index(index)
    mainClient.create_index(index, schema)
    mainClient.index_documents(index, movieDict)

def run(settings=None):
    # Recreate the index
    if settings is None:
        with open('data/settings.json') as src:
            settings = json.load(src)

    reindex(movieDict=json.load(open('data/tmdb.json')), schema=settings, index='tmdb')

    print('Done')

if __name__ == "__main__":
    run()
