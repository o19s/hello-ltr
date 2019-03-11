import requests

def run():
    resources = [
        'https://dl.bintray.com/o19s/RankyMcRankFace/com/o19s/RankyMcRankFace/0.1.1/RankyMcRankFace-0.1.1.jar',
        'http://es-learn-to-rank.labs.o19s.com/tmdb.json'
    ]

    def download(uri):
        filename = uri[uri.rfind('/') + 1:]
        with open('data/{}'.format(filename), 'wb') as out:
            print('GET {}'.format(uri))
            resp = requests.get(uri, stream=True)
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    out.write(chunk)

    for uri in resources:
        download(uri)

    print('Done.')
