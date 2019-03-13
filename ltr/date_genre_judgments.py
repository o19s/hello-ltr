import requests
try:
    from judgments import Judgment, judgmentsToFile
except ImportError:
    from .judgments import Judgment, judgmentsToFile

def genreQid(genre):
    if genre == "Science Fiction":
        return 1
    if genre == "Drama":
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
        if releaseYear > 2015:
            return 4
        elif releaseYear > 2010:
            return 3
        elif releaseYear > 2000:
            return 2
        elif releaseYear > 1990:
            return 1
        else:
            return 0

    if movie['genres'][0] == "Drama":
        if releaseYear > 1990:
            return 0
        elif releaseYear > 1970:
            return 1
        elif releaseYear > 1950:
            return 2
        elif releaseYear > 1930:
            return 3
        else:
            return 4
    return 0


def buildJudgments(judgmentsFile='genre_by_date_judgments.txt', autoNegate=False):
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
            genre=movie['genres'][0]
            qid = genreQid(genre)
            if qid == 0:
                continue
            judgment = Judgment(qid=qid,
                                grade=genreGrade(movie),
                                docId=doc['_id'],
                                keywords=genre)
            judgments.append(judgment)

            # This movie is good for its genre, but
            # a bad result for the opposite genre
            negGenre = None
            if genre == "Science Fiction":
                negGenre = "Drama"
            elif genre == "Drama":
                negGenre = "Science Fiction"

            if autoNegate and negGenre is not None:
                negQid=genreQid(negGenre)
                judgment = Judgment(qid=negQid,
                                    grade=0,
                                    docId=doc['_id'],
                                    keywords=negGenre)
                judgments.append(judgment)

    judgmentsToFile(judgmentsFile, judgmentsList=judgments)

    print('Done')
    return judgments


if __name__ == "__main__":
    buildJudgments(autoNegate=True)
