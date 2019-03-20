def setup(client, config, featureset='genre_features'):
    client.reset_ltr()
    client.create_featureset('tmdb', featureset, config)
