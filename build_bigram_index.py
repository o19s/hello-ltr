import csv
import sys

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


def reorder_term_vectors(termvects):
    slots = []
    for term, posns in termvects.items():
        for posn in posns['positions']:
            try:
                slots[posn]
            except IndexError:
                slots.extend([None] * (1 + (posn - len(slots))))
            if slots[posn] is not None:
                print("Two terms in %s: (%s,%s)" % (posn, term, slots[posn]))
            slots[posn] = term
    assert len(slots) == 0 or slots[-1] != None # We should only have grown the list to accomidate the terms
    return slots




from ltr.helpers.colocations.bigram_index import BigramIndex
from ltr.client import SolrClient

def marcoBigrams(fname=None, start_at=0, save_every=20000):
    bigram_index = BigramIndex()
    # load locally cached file
    if fname:
        bigram_index = BigramIndex.from_pkl(fname)

    client = SolrClient()

    start_cursor = '*'
    if (start_at > 0):
        start_cursor = client.term_vectors_skip_to(index='msmarco', skip=start_at)
    print("Restarting at cursor %s" % start_cursor)

    i = start_at
    for doc_id, body_vects in client.term_vectors(index='msmarco', field='body', start_cursor=start_cursor):
        terms = reorder_term_vectors(body_vects)
        bigram_index.add_doc(terms)
        if i % 100 == 0:
            print("Gathered %s; terms %s" % (i, len(bigram_index.term_dict.term_to_ord)))
        if i % save_every == (save_every - 1):
            print("Dumped %s docs" % i)
            bigram_index.dump('.cache/marco_bigrams_' + str(i) + '.pkl')
        i+=1

    return bigram_index

if __name__ == "__main__":
    start_at = 0
    fname = None
    from sys import argv
    if len(argv) > 1:
        pick_up_from = int(argv[1])
        start_at = pick_up_from + 1
        fname = '.cache/marco_bigrams_' + str(pick_up_from) + '.pkl'
    bigram_index = marcoBigrams(fname=fname, start_at=start_at)
    bigram_index.dump('marco_bigrams.pkl')

    for term1, term2, tf in bigram_index.common_n_bigrams(50):
        print(term1, term2, tf)


    #coloc = Colocations(bigram_index)
    #scored_bigrams = coloc.score_all(min_term_count=10)
    #with open('colocs.txt', 'w') as f:
    #    for i in range(0,10000):
    #        bg = scored_bigrams.pop()
    #        f.write("%s %s %s => %s\n" % (bg[0], bg[1], bg[2], "%s_%s" % (bg[1],bg[2])))


