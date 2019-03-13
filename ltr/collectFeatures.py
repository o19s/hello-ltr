logQuery = {
    "size": 10000,
    "query": {
        "bool": {
            "must": [
                {
                    "terms": {
                        "_id": ["7555"]

                    }
                }
            ],
            "should": [
                {"sltr": {
                    "_name": "logged_featureset",
                    "featureset": "movie_features",
                    "params": {
                        "keywords": "rambo"
                    }
                }}
                ]
            }
    },
    "ext": {
        "ltr_log": {
            "log_specs": {
                "name": "main",
                "named_query": "logged_featureset",
                "missing_as_zero": True

            }
        }
    }
}

def featureDictToList(ranklibLabeledFeatures):
    rVal = [0.0] * len(ranklibLabeledFeatures)
    for idx, logEntry in enumerate(ranklibLabeledFeatures):
        value = logEntry['value']
        try:
            rVal[idx] = value
        except IndexError:
            print("Out of range %s" % idx)
    return rVal


def logFeatures(es, judgmentsByQid, featureSet):
    idx = 0
    for qid, judgments in judgmentsByQid.items():
        keywords = judgments[0].keywords
        featuresPerDoc = {}
        docIds = [judgment.docId for judgment in judgments]

        # For every batch of N docs to generate judgments for
        BATCH_SIZE = 500
        numLeft = len(docIds)
        for i in range(0, 1 + (len(docIds) // BATCH_SIZE)):

            numFetch = min(BATCH_SIZE, numLeft)
            start = i*BATCH_SIZE
            if start >= len(docIds):
                break

            logQuery['query']['bool']['must'][0]['terms']['_id'] = docIds[start:start+numFetch]
            logQuery['query']['bool']['should'][0]['sltr']['params']['keywords'] = keywords
            logQuery['query']['bool']['should'][0]['sltr']['featureset'] = featureSet
            res = es.search(index='tmdb', body=logQuery)
            # print("...done")
            # Add feature back to each judgment
            for doc in res['hits']['hits']:
                docId = doc['_id']
                features = doc['fields']['_ltrlog'][0]['main']
                featuresPerDoc[docId] = featureDictToList(features)
            numLeft -= BATCH_SIZE

        print("REBUILDING TRAINING DATA for %s (%s/%s)" % (judgments[0].keywords, idx, len(judgmentsByQid)))
        # Append features from ES back to ranklib judgment list
        for judgment in judgments:
            try:
                features = featuresPerDoc[judgment.docId] # If KeyError, then we have a judgment but no movie in index
                judgment.features = features
            except KeyError:
                pass
                print("Missing movie %s" % judgment.docId)
        idx += 1


def trainingSetFromJudgments(judgmentInFile, featureSet, trainingOutFile='judgments_wfeatures.txt'):
    from elasticsearch import Elasticsearch
    try:
        from .judgments import judgmentsToFile, judgmentsFromFile, judgmentsByQid
    except ImportError:
        from judgments import judgmentsToFile, judgmentsFromFile, judgmentsByQid

    es = Elasticsearch('http://localhost:9200')
    judgments = judgmentsFromFile(judgmentInFile)
    judgments = judgmentsByQid(judgments)
    logFeatures(es, judgments, featureSet=featureSet)

    judgmentsAsList = []
    for qid, judgmentList in judgments.items():
        for judgment in judgmentList:
            judgmentsAsList.append(judgment)

    judgmentsToFile(filename=trainingOutFile, judgmentsList=judgmentsAsList)
    return judgments



def buildFeaturesJudgmentsFile(judgmentsWithFeatures, filename):
    with open(filename, 'w') as judgmentFile:
        for qid, judgmentList in judgmentsWithFeatures.items():
            for judgment in judgmentList:
                judgmentFile.write(judgment.toRanklibFormat() + "\n")


if __name__ == "__main__":
    trainingSetFromJudgments(judgmentInFile='genre_by_date_judgments.txt',
                                         trainingOutFile='genre_by_date_judgments_train.txt',
                                         featureSet='genre')

