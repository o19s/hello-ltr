import json

movies=json.load(open('data/tmdb.json'))

def get_movie(tmdb_id):
    tmdb_id=str(tmdb_id)
    global movies
    return movies[tmdb_id]


def noop(src_movie, base_doc):
    return base_doc


def indexable_movies(enrich=noop):
    """ Generates TMDB movies, similar to how ES Bulk indexing
        uses a generator to generate bulk index/update actions """
    global movies
    for movieId, tmdbMovie in movies.items():
        try:
            releaseDate = None
            if 'release_date' in tmdbMovie and len(tmdbMovie['release_date']) > 0:
                releaseDate = tmdbMovie['release_date']
                releaseYear = releaseDate[0:4]

            base_doc = {'id': movieId,
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
            yield enrich(tmdbMovie, base_doc)
        except KeyError as k: # Ignore any movies missing these attributes
            print("Skipping %s" % movieId)
            continue


