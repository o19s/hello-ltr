from ltr.MART_model import eval_model
from ltr.client import ElasticClient
from ltr.judgments import judgments_from_file

client = ElasticClient()
features, _ = client.feature_set(index='tmdb', name='title')

judgments = judgments_from_file(filename='data/title_judgments_train.txt')
judgments = [judgment for judgment in judgments]
model = eval_model(modelName='title',
                   features=features,
                   judgments=judgments)
model.whoopsies()

print(str(model))
