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

def run(client, featureSet='release', latestTrainingSetOut='data/latest-training.txt', classicTrainingSetOut='data/classic-training.txt'):
    print('Generating ratings for classic and latest model')
    NO_ZERO = False

    resp = client.log_query('tmdb', 'release', None)

    docs = []
    for hit in resp:
        # Expect clients to return features per doc in ltr_features as ordered list
        feature = hit['ltr_features'][0]

        docs.append([feature]) # Treat features as ordered lists

    # Classic film fan
    with open(classicTrainingSetOut, 'w') as out:
        for fv in docs:
            rating = get_classic_rating(fv[0])

            if rating == 0 and NO_ZERO:
                continue

            out.write("{}\tqid:1\t1:{}\n".format(rating, fv[0]))

    # Newer film fan
    with open(latestTrainingSetOut, 'w') as out:
        for fv in docs:
            rating = get_latest_rating(fv[0])

            if rating == 0 and NO_ZERO:
                continue

            out.write("{}\tqid:1\t1:{}\n".format(rating, fv[0]))

    print('Done')




