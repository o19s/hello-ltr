import requests

def run():
    resources = [
        'http://es-learn-to-rank.labs.o19s.com/tmdb.json',
        'http://es-learn-to-rank.labs.o19s.com/RankyMcRankFace.jar'
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

if __name__ == "__main__":
    run()
