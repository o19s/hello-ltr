import json
import requests

def run():
    BATCH_SIZE = 250
    index_ep = 'http://localhost:9200/tmdb'

    # Drop the index
    resp = requests.delete(index_ep)
    print('DELETE INDEX: {}'.format(resp.status_code))

    # Recreate the index
    with open('data/settings.json') as src:
        settings = json.load(src)

    resp = requests.put(index_ep, json=settings)
    print('POST INDEX: {}'.format(resp.status_code))

    with open('data/tmdb.json') as src:
        docset = json.load(src)

    print('Indexing {} movies'.format(len(docset.keys())))
    for key, tmdbMovie in docset.items():
        try:
            releaseDate = None
            releaseYear = None
            if 'release_date' in tmdbMovie and len(tmdbMovie['release_date']) > 0:
                releaseDate = tmdbMovie['release_date']
                releaseYear = releaseDate[0:4]

            doc = {
                'id': key,
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

            # TODO: Use bulk api
            resp = requests.put('{}/movie/{}'.format(index_ep, key), json=doc)
        except KeyError as k:
            continue

    print('Done')
