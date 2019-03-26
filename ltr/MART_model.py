import xml.etree.ElementTree as ET
from ltr.judgments import judgments_by_qid

def fold_whoopsies(whoopsies1, whoopsies2):
    """ Merge whoopsies2 into whoopsies1 """
    whoopsies1.extend(whoopsies2)
    whoopsies1.sort(key=lambda x: (x.qid, 1000-x.size()))
    return whoopsies1

def dedup_whoopsies(sWhoopsies):
    mergedWhoopsies = iter(sWhoopsies)

    whoopsies = []
    whoopsie = None
    lastQid = -1
    try:
        while True:
            while whoopsie is None or lastQid == whoopsie.qid:
                whoopsie = next(mergedWhoopsies)
            whoopsies.append(whoopsie)
            lastQid = whoopsie.qid
    except StopIteration:
        pass
    return whoopsies


class MARTModel:
    def __init__(self, ranklib_xml, features):
        """ Create a MART model from a ranklib_ensemble
            (string w/ ranklib xml model output)
            using `features` - array of named features
            where the 0th item is ranklib feature 1
             [{'name': 'release_date'}, ...] """
        # Clean up header
        validXml = '\n'.join(ranklib_xml.split('\n')[7:])
        lambdaModel = ET.fromstring(validXml)

        # List of tuples (weight, root split)
        self.trees = []
        for node in lambdaModel:
            self.trees.append((float(node.attrib['weight']),
                              Split(node[0], features)) )

    def __str__(self):
        rVal = ""
        for tree in self.trees:
            weight = tree[0]
            tree = tree[1]
            rVal += tree.treeString(weight=weight)
            rVal += "\n\n"
        return rVal

    def whoopsies(self):
        """ After eval, what are the most glaring
            query-doc inconsistencies in the provided judgments
            over the whole ensemble """
        whoopsQueries = {}
        for tree in self.trees:
            treeWhoopsies = tree[1].whoopsies()

            for whoops in dedup_whoopsies(treeWhoopsies):
                if whoops.qid not in whoopsQueries:
                    whoopsQueries[whoops.qid] = [0,0,[]]
                whoopsQueries[whoops.qid][0] += 1
                whoopsQueries[whoops.qid][1] += whoops.size()
                whoopsQueries[whoops.qid][2].append("%s-%s" % (whoops.minGrade, whoops.maxGrade))

        whoopsReport = []
        for qid, queryReport in whoopsQueries.items():
            whoopsReport.append((qid, queryReport[0], queryReport[1], queryReport[2]))

        whoopsReport.sort(key=lambda x: (x[1], x[0]))

        for report in whoopsReport:
            print(report)

        return []



    def eval(self, judgments):
        for tree in self.trees:
            # weight = tree[0]
            tree = tree[1]
            tree.eval(judgments)


class Whoopsie:

    def __init__(self, qid, judgList,
                 minGrade, maxGrade,
                 minGradeDocId, maxGradeDocId,
                 output):
        self.qid = qid; self.judgList = judgList
        self.minGrade = minGrade; self.maxGrade = maxGrade
        self.minGradeDocId = minGradeDocId; self.maxGradeDocId = maxGradeDocId
        self.output = output

    def size(self):
        return self.maxGrade - self.minGrade


class EvalReport:

    def __init__(self, split):
        if split.output is None:
            raise ValueError("Split not a leaf")

        self.split = split
        self.count = len(split.evals)
        self.whoopsies = []

        self.computeWhoopsies()

    def computeWhoopsies(self):
        judgmentsByQid = judgments_by_qid(self.split.evals)
        report = []
        for qid, judgList in judgmentsByQid.items():
            if len(judgList) > 1:
                minGradeDocId = judgList[0].docId
                maxGradeDocId = judgList[0].docId
                minGrade = maxGrade = judgList[0].grade
                for judg in judgList:
                    if judg.grade < minGrade:
                        minGrade = judg.grade
                        minGradeDocId = judg.docId
                    if judg.grade > maxGrade:
                        maxGrade = judg.grade
                        maxGradeDocId = judg.docId
                if minGrade != maxGrade:
                    report.append(Whoopsie(qid=qid, judgList=judgList,
                                           minGrade=minGrade, maxGrade=maxGrade,
                                           minGradeDocId=minGradeDocId, maxGradeDocId=maxGradeDocId,
                                           output=self.split.output))
        report.sort(key=lambda x: x.maxGrade - x.minGrade, reverse=True)
        self.whoopsies = report

    def __str__(self):
        reportStr = ";".join(["qid:%s:%s(%s)-%s(%s)" % (report.qid, report.minGrade,
                                                        report.minGradeDocId,
                                                        report.maxGrade,
                                                        report.maxGradeDocId)
                            for report in self.whoopsies])
        return "%s/%s/%s" % (self.count, len(self.whoopsies), reportStr)

    def __repr__(self):
        return str(self)



class Split:
    def __init__(self, splitEl, features):
        self.feature = None     # Name of the feature
        self.featureOrd = None  # ONE BASED, feature ord in the ranklib model
        self.featureIdx = None  # Zero BASED - use for lookups
        self.threshold = None
        self.value = None
        self.left = None
        self.right = None
        self.output = None
        self.evalReport = None

        self.evals = []

        for el in splitEl:
            if (el.tag == 'feature'):
                self.featureOrd = int(el.text.strip())
                self.featureIdx = self.featureOrd - 1
                self.feature = features[self.featureIdx]['name']
            elif (el.tag == 'threshold'):
                self.threshold = float(el.text.strip())
            elif (el.tag == 'split' and 'pos' in el.attrib):
                if el.attrib['pos'] == 'right':
                    self.right = Split(splitEl=el, features=features)
                elif el.attrib['pos'] == 'left':
                    self.left = Split(splitEl=el, features=features)
                else:
                    raise ValueError("Unrecognized Split Pos {}".format(el.attrib['pos']))
            elif (el.tag == 'output'):
                self.output = float(el.text.strip())


    def clearEvals(self):
        """ Clear the eval state """
        if self.output:
            self.evals = []
            self.evalReport = None
        elif self.right:
            self.right.clearEvals()
        elif self.left:
            self.left.clearEvals()

    def _evalAppend(self, judgment):
        """ For model/feature analysis purposes, evaluate the model with
            the 'judgment' placing at each leaf the obj
            so we can analyze how well the model is classifying items

            Args:
            - judgment: some Python object with a features attribute
                               which is a list of floating point numbers where
                               0th corresponds to Ranklib's '1'th
            """
        if self.output:
            self.evals.append(judgment)
            return

        ftrToEval = self.featureIdx
        featureVal = judgment.features[ftrToEval]
        if featureVal > self.threshold:
            assert self.right is not None
            self.right._evalAppend(judgment)
        else:
            assert self.left is not None
            self.left._evalAppend(judgment)

    def _computeEvalStats(self):
        if self.output:
            self.evalReport = EvalReport(self)
            return
        else:
            assert self.right is not None
            assert self.left is not None
            self.right._computeEvalStats()
            self.left._computeEvalStats()

    def eval(self, judgments):
        self.clearEvals()
        for judgment in judgments:
            self._evalAppend(judgment)
        self._computeEvalStats()

    def whoopsies(self):
        """ Merge all the whoopsies from the child nodes into
            me """
        if self.output:
            if self.evalReport is None:
                return []
            return self.evalReport.whoopsies
        else:
            assert self.right is not None
            assert self.left is not None
            rWhoopsies = self.right.whoopsies()
            lWhoopsies = self.left.whoopsies()
            return fold_whoopsies(lWhoopsies, rWhoopsies)


    def treeString(self, weight=1.0, nestLevel=0):

        def idt(nestLevel):
            #return ("%s" % nestLevel) * 2 * nestLevel
            return (" ") * 2 * nestLevel

        rVal = ""
        if self.feature:
            rVal += idt(nestLevel)
            rVal +=  "if %s > %s:\n" % (self.feature, self.threshold)
            assert self.right is not None
            assert self.left is not None
            if self.right:
                rVal +=  self.right.treeString(weight=weight,
                                               nestLevel=nestLevel+1)
            if self.left:
                rVal += idt(nestLevel)
                rVal +=  "else:\n"
                rVal +=  self.left.treeString(weight=weight,
                                              nestLevel=nestLevel+1)
        if self.output:
            rVal += idt(nestLevel)
            rVal +=  "<= %.4f" % (self.output * weight)
            if self.evalReport:
                rVal += "(%s)" % self.evalReport
            rVal += "\n"
        return rVal


def dump_model(modelName, features):
    """ Print a model in pythoneque code

        Args:
            - modelName: The name of the model, will be read from data/modelName_name.txt
            - features: List of features, 0th item corresponding to Ranklib feature 1
                        each feature is an object with a 'name' parameter

    """
    with open('data/{}_model.txt'.format(modelName)) as f:
        ensembleXml = f.read()
        model = MARTModel(ensembleXml, features)
        for tree in model.trees:
            weight = tree[0]
            tree = tree[1]
            print(tree.treeString(weight=weight))

def eval_model(modelName, features, judgments):
    """ Evaluate a model relative to a list of judgments,
        return a model """

    judgmentList = [judgment for judgment in judgments]
    with open('data/{}_model.txt'.format(modelName)) as f:
        ensembleXml = f.read()
        model = MARTModel(ensembleXml, features)
        model.eval(judgmentList)
        return model
