# converts LambdaMART XML models to JSON for Solr..

import sys
import requests
import json
import xml.etree.ElementTree as ET


def convert(ensemble_xml_string, modelName, featureSet):
    features = []
    modelClass = 'org.apache.solr.ltr.model.MultipleAdditiveTreesModel'

    try:
        features = getFeatures(featureSet)
    except:
        print('>> error getting features..')
        return 1

    model = {
        'store': featureSet,
        'name': modelName,
        'class': modelClass,
        'features': features
    }


    # Clean up header
    ensemble_xml_string = '\n'.join(ensemble_xml_string.split('\n')[7:])
    lambdaModel = ET.fromstring(ensemble_xml_string)

    trees = []
    for node in lambdaModel:
        t = {
            'weight': str(node.attrib['weight']),
            'root': parseSplits(node[0], features)
        }
        trees.append(t)

    # print(trees)
    model['params'] = {'trees': trees}

    return model

def parseSplits(split, features):
    obj = {}
    for el in split:
        if (el.tag == 'feature'):
            obj['feature'] = features[(int(el.text.strip()) - 1)]['name']
        elif (el.tag == 'threshold'):
            obj['threshold'] = str(el.text.strip())
        elif (el.tag == 'split' and 'pos' in el.attrib):
            obj[el.attrib['pos']] = parseSplits(el, features)
        elif (el.tag == 'output'):
            obj['value'] = str(el.text.strip())
    return obj


def getFeatures(featureset):
    # TODO: Move this into solr client
    solrEndpoint = 'http://localhost:8983'
    r = requests.get('{}/solr/tmdb/schema/feature-store/{}'.format(solrEndpoint, featureset))

    response = r.json()

    fs = []
    for feature in response['features']:
        fs.append({'name': feature['name']})

    return fs
