import requests
from os import path

def download_one(uri, dest='data/', force=False):
    import os

    if not os.path.exists(dest):
        os.makedirs(dest)

    if not os.path.isdir(dest):
        raise ValueError("dest {} is not a directory".format(dest))

    filename = uri[uri.rfind('/') + 1:]
    filepath = os.path.join(dest, filename)
    if path.exists(filepath):
        if not force:
            print(filepath + ' already exists')
            return
        print("exists but force=True, Downloading anyway")

    with open(filepath, 'wb') as out:
        print('GET {}'.format(uri))
        resp = requests.get(uri, stream=True)
        for chunk in resp.iter_content(chunk_size=1024):
            if chunk:
                out.write(chunk)

def download(uris, dest='data/', force=False):
    for uri in uris:
        download_one(uri=uri, dest=dest, force=force)


def download_tmdb(force=False):
    resources = [
        'http://es-learn-to-rank.labs.o19s.com/tmdb.json',
        'http://es-learn-to-rank.labs.o19s.com/tmdb_2020-05-20.json',
        'http://es-learn-to-rank.labs.o19s.com/blog.jsonl',
        'http://es-learn-to-rank.labs.o19s.com/osc_judgments.txt',
        'http://es-learn-to-rank.labs.o19s.com/RankyMcRankFace.jar',
        'http://es-learn-to-rank.labs.o19s.com/title_judgments.txt',
        'http://es-learn-to-rank.labs.o19s.com/title_judgments_binary.txt',
        'http://es-learn-to-rank.labs.o19s.com/genome_judgments.txt',
        'http://es-learn-to-rank.labs.o19s.com/sample_judgments_train.txt'
    ]

    download(resources)
    print('Done.')

def download_msmarco(force=False):
    resources = [
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-docs.tsv.gz',
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-docs-lookup.tsv.gz',
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-doctrain-qrels.tsv.gz',
        'https://msmarco.blob.core.windows.net/msmarcoranking/msmarco-doctrain-queries.tsv.gz']
    download(resources)
    print('Done.')

