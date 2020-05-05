def setup(client, config, index, featureset):
    client.reset_ltr(index)
    client.create_featureset(index, featureset, config)


def setup_keep_old_models_features(client, config, index, featureset):
    client.create_featureset(index, featureset, config)
