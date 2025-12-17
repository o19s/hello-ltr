"""Model conversion utilities.

This module converts LambdaMART XML models (from RankLib) to JSON format
for use with Apache Solr's Learning-to-Rank plugin.
"""

import xml.etree.ElementTree as ET

from ltr.types import FeatureList, JSONDict, ModelPayload


def convert(
    ensemble_xml_string: str,
    model_name: str,
    feature_set: str,
    feature_mapping: FeatureList,
) -> ModelPayload:
    """Convert a LambdaMART XML model to Solr JSON format.

    Args:
        ensemble_xml_string: XML string containing the LambdaMART ensemble model.
        model_name: Name to assign to the model in Solr.
        feature_set: Name of the feature set/store to associate with this model.
        feature_mapping: List of feature dictionaries mapping feature indices
            to feature names.

    Returns:
        dict: Solr model configuration dictionary with:
            - store: Feature set name
            - name: Model name
            - class: Solr model class (MultipleAdditiveTreesModel)
            - features: Feature mapping
            - params: Model parameters including tree structures
    """
    model_class = "org.apache.solr.ltr.model.MultipleAdditiveTreesModel"

    model = {
        "store": feature_set,
        "name": model_name,
        "class": model_class,
        "features": feature_mapping,
    }

    # Clean up header
    ensemble_xml_string = "\n".join(ensemble_xml_string.split("\n")[7:])
    lambda_model = ET.fromstring(ensemble_xml_string)

    trees = []
    for node in lambda_model:
        t = {
            "weight": str(node.attrib["weight"]),
            "root": parse_splits(node[0], feature_mapping),
        }
        trees.append(t)

    # print(trees)
    model["params"] = {"trees": trees}

    return model


def parse_splits(split: ET.Element, features: FeatureList) -> JSONDict:
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
            obj[el.attrib["pos"]] = parse_splits(el, features)
        elif el.tag == "output":
            obj["value"] = str(el.text.strip())
    return obj
