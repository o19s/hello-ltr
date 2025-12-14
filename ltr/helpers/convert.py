"""Model conversion utilities.

This module converts LambdaMART XML models (from RankLib) to JSON format
for use with Apache Solr's Learning-to-Rank plugin.
"""

import xml.etree.ElementTree as ET


def convert(ensemble_xml_string, modelName, featureSet, featureMapping):
    """Convert a LambdaMART XML model to Solr JSON format.

    Args:
        ensemble_xml_string: XML string containing the LambdaMART ensemble model.
        modelName: Name to assign to the model in Solr.
        featureSet: Name of the feature set/store to associate with this model.
        featureMapping: List of feature dictionaries mapping feature indices
            to feature names.

    Returns:
        dict: Solr model configuration dictionary with:
            - store: Feature set name
            - name: Model name
            - class: Solr model class (MultipleAdditiveTreesModel)
            - features: Feature mapping
            - params: Model parameters including tree structures
    """
    modelClass = "org.apache.solr.ltr.model.MultipleAdditiveTreesModel"

    model = {
        "store": featureSet,
        "name": modelName,
        "class": modelClass,
        "features": featureMapping,
    }

    # Clean up header
    ensemble_xml_string = "\n".join(ensemble_xml_string.split("\n")[7:])
    lambdaModel = ET.fromstring(ensemble_xml_string)

    trees = []
    for node in lambdaModel:
        t = {
            "weight": str(node.attrib["weight"]),
            "root": parseSplits(node[0], featureMapping),
        }
        trees.append(t)

    # print(trees)
    model["params"] = {"trees": trees}

    return model


def parseSplits(split, features):
    """Recursively parse XML tree splits into Solr tree structure.

    Args:
        split: XML ElementTree element representing a tree node/split.
        features: List of feature dictionaries for mapping feature indices to names.

    Returns:
        dict: Tree node dictionary with:
            - feature: Feature name (if leaf node)
            - threshold: Split threshold value (if split node)
            - left/right: Child nodes (if split node)
            - value: Output value (if leaf node)
    """
    obj = {}
    for el in split:
        if el.tag == "feature":
            obj["feature"] = features[(int(el.text.strip()) - 1)]["name"]
        elif el.tag == "threshold":
            obj["threshold"] = str(el.text.strip())
        elif el.tag == "split" and "pos" in el.attrib:
            obj[el.attrib["pos"]] = parseSplits(el, features)
        elif el.tag == "output":
            obj["value"] = str(el.text.strip())
    return obj
