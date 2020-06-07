import re

def log_query(client, index, judgments, feature_set, drop_missing=True):
    """ Log a set of judgments associated with a single qid
        judgments will be modified, a training set also returned, discarding
        any judgments we could not log features for (because the doc was missing)
    """
    judgments = [j for j in judgments] # TODO make this more iterator/generator friendly

    keywords = judgments[0].keywords
    featuresPerDoc = {}
    docIds = [judgment.docId for judgment in judgments]
    qid = judgments[0].qid

    # Check for dups of documents
    for docId in docIds:
        indices = [i for i, x in enumerate(docIds) if x == docId]
        if len(indices) > 1:
            print("Duplicate Doc in qid:%s %s" % (qid, docId))

    # For every batch of N docs to generate judgments for
    BATCH_SIZE = 500
    numLeft = len(docIds)
    for i in range(0, 1 + (len(docIds) // BATCH_SIZE)):

        numFetch = min(BATCH_SIZE, numLeft)
        start = i*BATCH_SIZE
        if start >= len(docIds):
            break
        ids = docIds[start:start+numFetch]

        # Sanitize (Solr has a strict syntax that can easily be tripped up)
        # This removes anything but alphanumeric and spaces
        keywords = re.sub('([^\s\w]|_)+', '', keywords)

        params = {
            "keywords": keywords,
            "fuzzy_keywords": ' '.join([x + '~' for x in keywords.split(' ')])
        }

        res = client.log_query(index, feature_set, ids, params)

        # Add feature back to each judgment
        for doc in res:
            docId = str(doc['id'])
            features = doc['ltr_features']
            featuresPerDoc[docId] = features
        numLeft -= BATCH_SIZE

    # Append features from search engine back to ranklib judgment list
    for judgment in judgments:
        try:
            features = featuresPerDoc[judgment.docId] # If KeyError, then we have a judgment but no movie in index
            judgment.features = features
        except KeyError:
            pass
            print("Missing doc %s" % judgment.docId)

    # Return a paired down judgments if we are missing features for judgments
    training_set = []
    discarded = []
    for judgment in judgments:
        if drop_missing:
            if judgment.has_features():
                training_set.append(judgment)
            else:
                discarded.append(judgment)
        else:
            training_set.append(judgment)
    print("Discarded %s Keep %s" % (len(discarded), len(training_set)))
    return training_set, discarded


def log_all_features(client, index, judgments_by_qid, featureSet):
    idx = 0
    for qid, judgments in judgments_by_qid.items():
        log_query(client, index, judgments, feature_set=featureSet)
        print("REBUILDING TRAINING DATA for %s (%s/%s)" % (judgments[0].keywords, idx, len(judgments_by_qid)))
        idx += 1

def judgments_to_training_set(client, judgmentInFile, featureSet, trainingOutFile='judgments_wfeatures.txt', index='tmdb'):
    from .judgments import judgments_to_file, judgments_from_file, judgments_by_qid

    judgments = []
    with open(judgmentInFile) as f:
        judgments = judgments_from_file(f)
        judgments = judgments_by_qid(judgments)
    log_all_features(client, index, judgments, featureSet=featureSet)

    judgmentsAsList = []
    discarded = []
    for qid, judgmentList in judgments.items():
        for judgment in judgmentList:
            if judgment.has_features():
                judgmentsAsList.append(judgment)
            else:
                discarded.append(judgment)
    print("Discarded %s Keep %s" % (len(discarded), len(judgmentsAsList)))

    with open(trainingOutFile, 'w+') as f:
        judgments_to_file(f, judgmentsList=judgmentsAsList)
    return judgments
