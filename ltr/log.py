import re

class FeatureLogger:
    """ Logs LTR Features, one query at a time

        ...Building up a training set...
    """

    def __init__(self, client, index, feature_set, drop_missing=True):
        self.client=client
        self.index=index
        self.feature_set=feature_set
        self.drop_missing=drop_missing
        self.logged=[]

    def clear(self):
        self.logged=[]

    def log_for_qid(self, qid, judgments, keywords):
        """ Log a set of judgments associated with a single qid
            judgments will be modified, a training set also returned, discarding
            any judgments we could not log features for (because the doc was missing)
        """
        featuresPerDoc = {}
        judgments = [j for j in judgments]
        docIds = [judgment.docId for judgment in judgments]

        # Check for dups of documents
        for docId in docIds:
            indices = [i for i, x in enumerate(docIds) if x == docId]
            if len(indices) > 1:
                # print("Duplicate Doc in qid:%s %s" % (qid, docId))
                pass

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

            res = self.client.log_query(self.index, self.feature_set, ids, params)

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
                # print("Missing doc %s" % judgment.docId)

        # Return a paired down judgments if we are missing features for judgments
        training_set = []
        discarded = []
        for judgment in judgments:
            if self.drop_missing:
                if judgment.has_features():
                    training_set.append(judgment)
                else:
                    discarded.append(judgment)
            else:
                training_set.append(judgment)
        # print("Discarded %s Keep %s" % (len(discarded), len(training_set)))
        self.logged.extend(training_set)
        return training_set, discarded
