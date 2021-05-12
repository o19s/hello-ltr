def get_classic_rating(year):
    if year > 2010:
        return 0
    elif year > 1990:
        return 1
    elif year > 1970:
        return 2
    elif year > 1950:
        return 3
    else:
        return 4

def get_latest_rating(year):
    if year > 2010:
        return 4
    elif year > 1990:
        return 3
    elif year > 1970:
        return 2
    elif year > 1950:
        return 1
    else:
        return 0

import json
def synthesize(client, featureSet='release', latestTrainingSetOut='data/latest-training.txt', classicTrainingSetOut='data/classic-training.txt'):
    from ltr.judgments import judgments_to_file, Judgment
    print('Generating ratings for classic and latest model')
    NO_ZERO = False

    resp = client.log_query('tmdb', 'release', None)

    # Classic film fan
    judgments = []
    print("Generating Classic judgments:")
    for hit in resp:
        rating = get_classic_rating(hit['ltr_features'][0])

        if rating == 0 and NO_ZERO:
            continue

        judgments.append(Judgment(qid=1,docId=hit['id'],grade=rating,features=hit['ltr_features'],keywords=''))

    with open(classicTrainingSetOut, 'w') as out:
        judgments_to_file(out, judgments)

    # Latest film fan
    judgments = []
    print("Generating Recent judgments:")
    for hit in resp:
        rating = get_latest_rating(hit['ltr_features'][0])

        if rating == 0 and NO_ZERO:
            continue

        judgments.append(Judgment(qid=1,docId=hit['id'],grade=rating,features=hit['ltr_features'],keywords=''))


    with open(latestTrainingSetOut, 'w') as out:
        judgments_to_file(out, judgments)





