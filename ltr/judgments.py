import re
from contextlib import contextmanager

class JudgmentsWriter:
    """ Wraps writing to file descriptor for
        a list of judgments """
    def __init__(self, f):
        self.f = f
        self.judgments=[]

    def write(self, judgment=None, judgments=None):
        if judgment is not None:
            self.judgments.append(judgment)
        elif judgments is not None:
            self.judgments.extend(judgments)

    def flush(self):
        judgments_to_file(self.f, self.judgments)


class JudgmentsReader:
    """ Wraps reading from file descriptor for
     lazy judgment reading..."""
    def __init__(self, f):
        self.f = f
        self.kw_with_weight = _queriesFromHeader(f)
        self.judgments = _judgment_rows(f, self.kw_with_weight)

    def keywords(self, qid):
        return self.kw_with_weight[qid][0]

    def __iter__(self):
        return self.judgments

@contextmanager
def judgments_open(path=None, mode='r'):
    """ Work with judgments from the filesystem,
        either in a read or write mode"""
    try:
        f=open(path, mode)
        if mode[0] == 'r':
            yield JudgmentsReader(f)
        elif mode[0] == 'w':
            writer = JudgmentsWriter(f)
            yield writer
            writer.flush()
    finally:
        f.close()

@contextmanager
def judgments_writer(f):
    """ Write to a judgment list at
        the provided file descripter (like StringIO)"""
    try:
        writer = JudgmentsWriter(f)
        yield writer
    finally:
        writer.flush()
        pass

@contextmanager
def judgments_reader(f):
    """ Read from a judgment list at
        the provided file descripter (like StringIO)"""
    try:
        yield JudgmentsReader(f)
    finally:
        pass

class Judgment:
    def __init__(self, grade, qid, keywords, docId, features=[], weight=1):
        self.grade = grade
        self.qid = qid
        self.keywords = keywords
        self.docId = docId
        self.features = features # 0th feature is ranklib feature 1
        self.weight = weight

    def sameQueryAndDoc(self, other):
        return self.qid == other.qid and self.docId == other.docId

    def has_features(self):
        return self.features is not None and (len(self.features) > 0)

    def __str__(self):
        return "grade:%s qid:%s (%s) docid:%s" % (self.grade, self.qid, self.keywords, self.docId)

    def __repr__(self):
        return "Judgment(grade={grade},qid={qid},keywords={keywords},docId={docId},features={features},weight={weight}".format(**vars(self))

    def toRanklibFormat(self):
        featuresAsStrs = ["%s:%s" % (idx+1, feature) for idx, feature in enumerate(self.features)]
        comment = "# %s\t%s" % (self.docId, self.keywords)
        return "%s\tqid:%s\t%s %s" % (self.grade, self.qid, "\t".join(featuresAsStrs), comment)


def _queriesToHeader(qidToKwDict):
    rVal = ""
    for qid, kws in qidToKwDict.items():
        rVal += "# qid:%s: %s" % (qid, kws[0])
        rVal += "*%s\n" % kws[1]
    rVal += "\n"
    return rVal


def _queriesFromHeader(lines):
    """ Parses out mapping between, query id and user keywords
        from header comments, ie:
        # qid:523: First Blood
        returns dict mapping all query ids to search keywords"""
    # Regex can be debugged here:
    # http://www.regexpal.com/?fam=96564
    regex = re.compile('#\sqid:(\d+?):\s+?(.*)')
    rVal = {}
    for line in lines:
        if line[0] != '#':
            break
        m = re.match(regex, line)
        try:
            if m:
                keywordAndWeight = m.group(2).split('*')
                keyword = keywordAndWeight[0]
                weight = 1
                if len(keywordAndWeight) > 1:
                    weight = int(keywordAndWeight[-1])
                rVal[int(m.group(1))] = (keyword, weight)
        except ValueError as e:
            print(e)
#    print("Recognizing %s queries in: %s" % (len(rVal), lines.name))
    print("Recognizing %s queries" % len(rVal))

    return rVal

def _judgmentsFromBody(lines):
    """ Parses out judgment/grade, query id, docId, and possibly features in line such as:
         4  qid:523   # a01  Grade for Rambo for query Foo

         Or

         4  qid:523  1:42.6 2:0.5  # a01  Grade for Rambo for query Foo
        <judgment> qid:<queryid> # docId <rest of comment ignored...)"""
    # Regex can be debugged here:
    # http://www.regexpal.com/?fam=96565
    regex = re.compile('^(\d+)\s+qid:(\d+)\s+#\s+(\w+).*')
    trainRegex = re.compile('^(\d+)\s+qid:(\d+)\s+1:\d+.+#\s+(\w+).*')
    ftrRegex = re.compile('(\d+):([.\d]+)\s')
    for line in lines:
        m = re.match(regex, line)
        if m:
            yield int(m.group(1)), int(m.group(2)), m.group(3), []
        else:
            m = re.match(trainRegex, line)
            if m:
                grade = int(m.group(1))
                qid = int(m.group(2))
                docId = m.group(3)
                ftrMatches = re.finditer(ftrRegex, line)

                features = {}
                ftrSize = 0

                for m in ftrMatches:
                    ftrIdx = int(m.group(1)) - 1
                    if ftrIdx + 1 > ftrSize:
                        ftrSize = ftrIdx + 1
                    ftrScore = float(m.group(2))
                    features[ftrIdx] = ftrScore

                featuresList = [None] * ftrSize
                for ftrIdx, value in features.items():
                    featuresList[ftrIdx] = value

                for featureVal in featuresList:
                    if featureVal is None:
                        raise ValueError("Missing Features Detected When Parsing Training Set")

                yield grade, qid, docId, featuresList

            pass
            #print("Not Recognized as Judgment %s" % line)


def _judgment_rows(f, qidToKeywords):
    lastQid = -1
    for grade, qid, docId, features in _judgmentsFromBody(f):
        if qid < lastQid:
            raise ValueError("Judgments not sorted by qid in file")
        # if lastQid != qid and qid % 100 == 0:
        #     print("Parsing QID %s" % qid)
        yield Judgment(grade=grade, qid=qid,
                       keywords=qidToKeywords[qid][0],
                       weight=qidToKeywords[qid][1],
                       docId=docId,
                       features=features)
        lastQid = qid


def judgments_from_file(f):
    """ Read judgments from a SVMRank File
        f is a file object
    """
    qidToKeywords = _queriesFromHeader(f)
    yield from _judgment_rows(f, qidToKeywords)

def judgments_to_file(f, judgmentsList):
    """ Write judgments from a SVMRank File
        f is a file object
    """
    # TODO - consider if a groupby approach would work instead of needing everything in memory
    judgToQid = _judgments_by_qid(judgmentsList) #Pretty hideosly slow stuff
    fileHeader = _queriesToHeader({qid: (judgs[0].keywords, judgs[0].weight) for qid, judgs in judgToQid.items()})
    judgByQid = sorted(judgmentsList, key=lambda j: j.qid)
    f.write(fileHeader)
    for judg in judgByQid:
        f.write(judg.toRanklibFormat() + '\n')




def _judgments_by_qid(judgments):
    """ Create a dictionary of qid->judgments
        Prefer itertools groupby"""
    rVal = {}
    for judgment in judgments:
        try:
            rVal[judgment.qid].append(judgment)
        except KeyError:
            rVal[judgment.qid] = [judgment]
    return rVal

def judgments_to_nparray(judgments):
    """ Return
        - features - num samples x num features
        - predictors - num samples x grade, qid
    """
    import numpy as np
    predictors = []
    features = []
    for idx, judg in enumerate(judgments):
        predictors.append([judg.grade, judg.qid])
        features.append(judg.features)
    features = np.array(features)
    predictors = np.array(predictors)
    return features, predictors

def judgments_to_dataframe(judgments, unnest = True):
    import pandas as pd
    ret = []
    for j in judgments:
        ret.append(
            {
                "uid": str(j.qid) + '_' + j.docId,
                "qid": j.qid,
                "keywords": j.keywords,
                "docId": j.docId,
                "grade": j.grade,
                "features": j.features
            }
        )
    dat = pd.DataFrame.from_dict(ret)

    # https://stackoverflow.com/questions/53218931/how-to-unnest-explode-a-column-in-a-pandas-dataframe
    def unnesting(df, explode):
        df1 = pd.concat([
                        pd.DataFrame(df[x].tolist(), index=df.index).add_prefix(x) for x in explode], axis=1)
        return df1.join(df.drop(explode, axis=1), how='left')

    if unnest:
        dat = unnesting(dat, ['features'])

    return dat

def judgments_dataframe_to_long(judgments_df):
    import pandas as pd
    
    return pd.wide_to_long(judgments_df, ['features'], i='uid', j='feature_id').reset_index()

def duplicateJudgmentsByWeight(judgmentsByQid):

    def copyJudgments(srcJudgments):
        destJudgments = []
        for judg in srcJudgments:
            destJudgments.append(Judgment(grade=judg.grade,
                                          qid=judg.qid,
                                          keywords=judg.keywords,
                                          weight=judg.weight,
                                          docId=judg.docId))
        return destJudgments

    rVal = {}
    maxQid = 0
    for qid, judgments in judgmentsByQid.items():
        maxQid = qid
    for qid, judgments in judgmentsByQid.items():
        rVal[qid] = judgments
        if (qid % 100 == 0):
            print("Duping %s" % qid)
        if (judgments[0].weight > 1):
            for i in range(judgments[0].weight - 1):
                rVal[maxQid] = copyJudgments(judgments)
                for judg in judgments:
                    judg.qid = maxQid
                maxQid += 1


    return rVal
