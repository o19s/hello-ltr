import re

class Judgment:
    def __init__(self, grade, qid, keywords, docId, weight=1):
        self.grade = grade
        self.qid = qid
        self.keywords = keywords
        self.docId = str(int(docId)) # To force ValueError
        self.features = [] # 0th feature is ranklib feature 1
        self.weight = weight

    def sameQueryAndDoc(self, other):
        return self.qid == other.qid and self.docId == other.docId

    def __str__(self):
        return "grade:%s qid:%s (%s) docid:%s" % (self.grade, self.qid, self.keywords, self.docId)

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
            import pdb; pdb.set_trace()
            print(e)
    print("Recognizing %s queries..." % len(rVal))

    return rVal

def _judgmentsFromBody(lines):
    """ Parses out judgment/grade, query id, and docId in line such as:
         4  qid:523   # a01  Grade for Rambo for query Foo
        <judgment> qid:<queryid> # docId <rest of comment ignored...)"""
    # Regex can be debugged here:
    # http://www.regexpal.com/?fam=96565
    regex = re.compile('^(\d+)\s+qid:(\d+)\s+#\s+(\w+).*')
    for line in lines:
        m = re.match(regex, line)
        if m:
            yield int(m.group(1)), int(m.group(2)), m.group(3)
        else:
            pass
            #print("Not Recognized as Judgment %s" % line)


def judgments_from_file(filename):
    with open(filename) as f:
        qidToKeywords = _queriesFromHeader(f)
    with open(filename) as f:
        lastQid = -1
        for grade, qid, docId in _judgmentsFromBody(f):
            if lastQid != qid and qid % 100 == 0:
                print("Parsing QID %s" % qid)
            yield Judgment(grade=grade, qid=qid, keywords=qidToKeywords[qid][0], weight=qidToKeywords[qid][1], docId=docId)
            lastQid = qid


def judgments_to_file(filename, judgmentsList):
    judgToQid = judgments_by_qid(judgmentsList) #Pretty hideosly slow stuff
    fileHeader = _queriesToHeader({qid: (judgs[0].keywords, judgs[0].weight) for qid, judgs in judgToQid.items()})
    judgByQid = sorted(judgmentsList, key=lambda j: j.qid)
    with open(filename, 'w+') as f:
        f.write(fileHeader)
        for judg in judgByQid:
            f.write(judg.toRanklibFormat() + '\n')




def judgments_by_qid(judgments):
    rVal = {}
    for judgment in judgments:
        try:
            rVal[judgment.qid].append(judgment)
        except KeyError:
            rVal[judgment.qid] = [judgment]
    return rVal


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
