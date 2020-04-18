import utils
from ltr.judgments import judgments_from_file
from ltr.client import ElasticClient
import csv


def train_to_csv(client, feature_set, in_filename, out_filename):
    features = client.feature_set(name=feature_set, index='tmdb')[0]
    fieldnames = ['keywords', 'qid', 'grade']
    fieldnames.extend([feature['name'] for feature in features])
    with open(out_filename, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        judgments = judgments_from_file(filename='data/title_judgments_train.txt')
        for judgment in judgments:
            assert len(judgment.features) == len(fieldnames) - 3
            record = {}
            record[fieldnames[0]] = judgment.keywords
            record[fieldnames[1]] = judgment.qid
            record[fieldnames[2]] = judgment.grade
            for idx,field in enumerate(fieldnames[3:]):
                record[field] = judgment.features[idx]

            writer.writerow(record)

if __name__ == "__main__":
    from sys import argv
    client = ElasticClient()
    train_to_csv(client=client, in_filename=argv[1],
                 feature_set=argv[2], out_filename=argv[3])



