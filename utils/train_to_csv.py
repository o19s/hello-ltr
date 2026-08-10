import csv

from ltr.client import ElasticClient
from ltr.judgments import judgments_from_file


def train_to_csv(client, feature_set, in_filename, out_filename):
    """Convert a RankLib training file to CSV format.

    Reads judgments from a RankLib-format file and writes them to a CSV file
    with columns for keywords, qid, grade, and all feature values.

    Args:
        client: Search client instance (used to fetch feature set metadata).
        feature_set: Name of the feature set to use for column names.
        in_filename: Path to input RankLib-format judgments file.
        out_filename: Path to output CSV file.

    Raises:
        AssertionError: If the number of features doesn't match the feature set.
    """
    features = client.feature_set(name=feature_set, index="tmdb")[0]
    fieldnames = ["keywords", "qid", "grade"]
    fieldnames.extend([feature["name"] for feature in features])
    with open(out_filename, "w", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        with open(in_filename, encoding="utf-8") as f:
            judgments = judgments_from_file(f)
            for judgment in judgments:
                assert len(judgment.features) == len(fieldnames) - 3
                record = {}
                record[fieldnames[0]] = judgment.keywords
                record[fieldnames[1]] = judgment.qid
                record[fieldnames[2]] = judgment.grade
                for idx, field in enumerate(fieldnames[3:]):
                    record[field] = judgment.features[idx]

                writer.writerow(record)


if __name__ == "__main__":
    from sys import argv

    client = ElasticClient()
    train_to_csv(
        client=client, in_filename=argv[1], feature_set=argv[2], out_filename=argv[3]
    )
