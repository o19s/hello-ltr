import requests
from os import path

def download_uri(uri):
    import os

    if not os.path.exists('data'):
        os.makedirs('data')

    filename = uri[uri.rfind('/') + 1:]
    filepath = 'data/{}'.format(filename)
    if path.exists(filepath):
        print(filepath + ' already exists')
        return

    with open(filepath, 'wb') as out:
        print('GET {}'.format(uri))
        resp = requests.get(uri, stream=True)
        for chunk in resp.iter_content(chunk_size=1024):
            if chunk:
                out.write(chunk)


def download():
    resources = [
        'http://es-learn-to-rank.labs.o19s.com/tmdb.json',
        'http://es-learn-to-rank.labs.o19s.com/blog.jsonl',
        'http://es-learn-to-rank.labs.o19s.com/osc_judgments.txt',
        'http://es-learn-to-rank.labs.o19s.com/RankyMcRankFace.jar',
        'http://es-learn-to-rank.labs.o19s.com/title_judgments.txt',
        'http://es-learn-to-rank.labs.o19s.com/genome_judgments.txt',
        'http://es-learn-to-rank.labs.o19s.com/sample_judgments_train.txt'
    ]

    for uri in resources:
        download_uri(uri)

    print('Done.')

def download_msmarco():
    resources = [
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-docs.tsv.gz',
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-docs-lookup.tsv',
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-doctrain-qrels.tsv',
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-doctrain-queries.tsv']
    for uri in resources:
        download_uri(uri)

    print('Done.')

