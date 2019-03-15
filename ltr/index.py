import json
import elasticsearch.helpers
from elasticsearch import Elasticsearch


def indexableMovies(movieDict):
    """ Generates TMDB movies, similar to how ES Bulk indexing
        uses a generator to generate bulk index/update actions """
    for movieId, tmdbMovie in movieDict.items():
        try:
            releaseDate = None
            if 'release_date' in tmdbMovie and len(tmdbMovie['release_date']) > 0:
                releaseDate = tmdbMovie['release_date']
                releaseYear = releaseDate[0:4]

            yield {'id': movieId,
                   'title': tmdbMovie['title'],
                   'overview': tmdbMovie['overview'],
                   'tagline': tmdbMovie['tagline'],
                   'directors': [director['name'] for director in tmdbMovie['directors']],
                   'cast': " ".join([castMember['name'] for castMember in tmdbMovie['cast']]),
                   'genres': [genre['name'] for genre in tmdbMovie['genres']],
                   'release_date': releaseDate,
                   'release_year': releaseYear,
                   'vote_average': float(tmdbMovie['vote_average']) if 'vote_average' in tmdbMovie else None,
                   'vote_count': int(tmdbMovie['vote_count']) if 'vote_count' in tmdbMovie else 0,
                   }
        except KeyError as k: # Ignore any movies missing these attributes
            print("Skipping %s" % movieId)
            continue


def reindex(es, schema, movieDict={}, index='tmdb'):

    es.indices.delete(index, ignore=[400, 404])
    es.indices.create(index, body=schema)

    def bulkDocs(movieDict):
        for movie in indexableMovies(movieDict):
            addCmd = {"_index": index,
                      "_type": "movie",
                      "_id": movie['id'],
                      "_source": movie}
            yield addCmd
            if 'title' in movie:
                print("%s added to %s" % (movie['title'], index))

    elasticsearch.helpers.bulk(es, bulkDocs(movieDict), chunk_size=100)


def run(settings=None):
    # Recreate the index
    if settings is None:
        with open('data/settings.json') as src:
            settings = json.load(src)

    es = Elasticsearch('http://localhost:9200')
    reindex(es, movieDict=json.load(open('data/tmdb.json')), schema=settings, index='tmdb')

    print('Done')

if __name__ == "__main__":
    run()
