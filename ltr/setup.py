def setup(client, config, index, featureset):
    client.reset_ltr(index)
    client.create_featureset(index, featureset, config)
