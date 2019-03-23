import xml.etree.ElementTree as ET

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

    def treeString(self, weight=1.0, nestLevel=0):

        def idt(nestLevel):
            return " " * nestLevel

        rVal = ""
        if self.feature:
            rVal += idt(nestLevel) + "if %s > %s:\n" % (self.feature, self.threshold)
            assert self.right is not None
            assert self.left is not None
            if self.right:
                rVal += idt(nestLevel) + self.right.treeString(weight=weight,
                                                               nestLevel=nestLevel+1)
            if self.left:
                rVal += idt(nestLevel) + "else\n"
                rVal += idt(nestLevel) + self.left.treeString(weight=weight,
                                                              nestLevel=nestLevel+1)
        if self.output:
            rVal += idt(nestLevel) + "<= %s\n" % (self.output * weight)
        return rVal
