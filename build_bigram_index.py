import csv
import sys
import os
import gzip

csv.field_size_limit(sys.maxsize)

def marcoDocs():
    with open('data/msmarco-docs.tsv') as tsvfile:
        reader = csv.reader(tsvfile, delimiter='\t')
        i = 0
        for row in reader:

            yield {"id": row[0],
                   "url": row[1],
                   "title": row[2],
                   "body": row[3]}
            i+=1
            if i % 10 == 0:
                print("Dumped (%s/%s) %s" % (i, 3213835, row[1]))


def cached_term_vect_files(folder='.cache/'):
    for filename in os.listdir(folder):
        if filename.endswith('.csv.gz'):
            yield os.path.join(folder, filename)

def parse_where_in_terms_fname(fname): #terms_2339999.csv.gz
    try:
        where = int(fname.split('_')[1].split('.')[0])
        return where
    except ValueError:
        print("File not parsable: %s" %fname)
        return -1

from ltr.helpers.colocations.bigram_index import BigramIndex

def marco_bigrams(begin, end):

    for fname in cached_term_vect_files():
        where = parse_where_in_terms_fname(fname)
        if begin < where <= end:
            print("Processing %s" % fname)
            bigram_index = BigramIndex()
            with gzip.open(fname, 'rt') as f:
                rdr = csv.reader(f)
                for idx, row in enumerate(rdr):
                    bigram_index.add_doc(row[1:])
                    if idx % 1000 == 0:
                        print("%s rows processed from %s" % (idx, fname))
            print("Bigrams for %s.pkl" % fname)
            bigram_index.dump( fname + '_bigrams_pkl.gz')

if __name__ == "__main__":
    import sys
    marco_bigrams(int(sys.argv[1]), int(sys.argv[2]))
