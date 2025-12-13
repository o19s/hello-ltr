from os import path

import requests


def download_one(uri, dest="data/", force=False):
    import os

    if not os.path.exists(dest):
        os.makedirs(dest)

    if not os.path.isdir(dest):
        raise ValueError(f"dest {dest} is not a directory")

    filename = uri[uri.rfind("/") + 1 :]
    filepath = os.path.join(dest, filename)
    if path.exists(filepath):
        if not force:
            print(filepath + " already exists")
            return
        print("exists but force=True, Downloading anyway")

    with open(filepath, "wb") as out:
        print(f"GET {uri}")
        resp = requests.get(uri, stream=True)
        for chunk in resp.iter_content(chunk_size=1024):
            if chunk:
                out.write(chunk)


def download(uris, dest="data/", force=False):
    for uri in uris:
        download_one(uri=uri, dest=dest, force=force)
