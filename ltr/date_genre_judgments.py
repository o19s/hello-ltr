import requests
try:
    from judgments import Judgment, judgmentsToFile
except ImportError:
    from .judgments import Judgment, judgmentsToFile

def genreQid(movie):
    if movie['genres'][0] == "Science Fiction":
        return 1
    if movie['genres'][0] == "Drama":
        return 2
    else:
        return 0


def genreGrade(movie):
    """ Create a simple training set, as if we were
        searching for a genre.

        Newer science fiction is considered better
        Older drama is considered better

        """
    if 'release_year' in movie and movie['release_year'] is not None:
        releaseYear = int(movie['release_year'])
    else:
        return 0
    if movie['genres'][0] == "Science Fiction":
        if releaseYear > 2010:
            return 4
        elif releaseYear > 1990:
            return 3
        elif releaseYear > 1970:
            return 2
        elif releaseYear > 1950:
            return 1
        else:
            return 0

    if movie['genres'][0] == "Drama":
        if releaseYear > 2010:
            return 0
        elif releaseYear > 1990:
            return 1
        elif releaseYear > 1970:
            return 2
        elif releaseYear > 1950:
            return 3
        else:
            return 4


def buildJudgments(judgmentsFile='genre_by_date_judgments.txt'):
    print('Generating judgments for scifi & drama movies')
    elastic_ep = 'http://localhost:9200/tmdb/_search'

    params = {
        "query": {
            "match_all": {}
        },
        "size": 10000
    }

    resp = requests.post(elastic_ep, json=params).json()

    # Build judgments for each film
    judgments = []
    for doc in resp['hits']['hits']:
        movie = doc['_source']
        if 'genres' in movie and len(movie['genres']) > 0:
            qid = genreQid(movie)
            if qid == 0:
                continue
            judgment = Judgment(qid=qid,
                                grade=genreGrade(movie),
                                docId=doc['_id'],
                                keywords=movie['genres'][0])
            judgments.append(judgment)
    judgmentsToFile(judgmentsFile, judgmentsList=judgments)
    print('Done')
    return judgments


if __name__ == "__main__":
    buildJudgments()
