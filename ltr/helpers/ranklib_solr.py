import json
from xml.etree import ElementTree

#
# Thanks Christine Poerschke
# taken from LTR w/ bees
# https://github.com/cpoerschke/ltr-with-bees/blob/master/py-wrappers/trees.py
#
def ranklibMartToSolr(ensemble_xml_string, modelName, featureSet, featureIndex2featureName):

  def transform_branches(root, featureIndex2featureName):

    # turn feature index into feature name
    for feature in root.findall("feature"):
      feature.text = featureIndex2featureName[int(feature.text)]

    for threshold in root.findall("threshold"):
        threshold.text = str(float(threshold.text))

    for branch in root.findall("split"):
      # turn <split> element with pos='???' attribute into <???> element
      branch.tag = branch.get("pos")

      # turn <output> element into <value> element
      for output in branch.findall("output"):
        output.tag = "value"
        output.text = str(float(output.text))

      # recurse
      transform_branches(branch, featureIndex2featureName)


  def parse_and_adjust_xml(xml_string):

    ensemble = ElementTree.fromstring(xml_string)

    for tree in ensemble.findall("tree"):

      # turn 'weight' attribute into 'weight' sub-element
      weight = ElementTree.SubElement(tree, 'weight')
      weight.text = str(tree.get("weight"))

      # rename tree root from <split> to <root>
      for root in tree.findall("split"):
        root.tag = "root"

        transform_branches(root, featureIndex2featureName)

    return ensemble


  def json_from_xml(input):

    if input.text != None and input.text.replace("\n","").replace("\t","") != "":

      return input.text

    else:

      return { elem.tag : json_from_xml(input.find(elem.tag)) for elem in list(input) }


  def trees_from_ensemble(xml_string):

    ensemble_xml = parse_and_adjust_xml(xml_string)

    return [ json_from_xml(tree) for tree in ensemble_xml.findall("tree") ]


  def features_set_from_trees(trees):

    features_set = set()

    def collect_features_from_tree(sub_tree):

      if 'feature' in sub_tree:
        features_set.add(sub_tree.get("feature"))

      if 'left' in sub_tree:
        collect_features_from_tree(sub_tree.get("left"))

      if 'right' in sub_tree:
        collect_features_from_tree(sub_tree.get("right"))

    for tree in trees:
      collect_features_from_tree(tree.get("root"))

    return [ { "name" : name } for name in features_set ]

  ensemble_xml_string = '\n'.join(ensemble_xml_string.split('\n')[7:])

  trees = trees_from_ensemble(ensemble_xml_string)
  features = list(features_set_from_trees(trees))

  treesModel = {
    "store": featureSet,
    "class" : "org.apache.solr.ltr.model.MultipleAdditiveTreesModel",
    "name" : modelName,
    "features" : features,
    "params" : { "trees" : trees }
  }
  return treesModel

def getModelType(modelTxt):
    # 0, MART
    # 1, RankNet
    # 2, RankBoost
    # 3, AdaRank
    # 4, coord Ascent
    # 6, LambdaMART
    # 7, ListNET
    # 8, Random Forests
    # 9, Linear Regression
    modelHeader = modelTxt.split('\n')[0]
    modelName = modelHeader[2:].strip()
    if modelName == "MART":
        return 0
    elif modelName == "RankNet":
        return 1
    elif modelName == "RankBoost":
        return 2
    elif modelName == "AdaRank":
        return 3
    if modelName == "LambdaMART":
        return 6
    print(modelName)
