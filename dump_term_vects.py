import csv
import gzip
from ltr.client import SolrClient
from datetime import datetime


def reorder_term_vectors(termvects):
    slots = []
    for term, posns in termvects.items():
        for posn in posns['positions']:
            try:
                slots[posn]
            except IndexError:
                slots.extend(['_'] * (1 + (posn - len(slots))))
            if slots[posn] is not '_':
                print("Two terms in %s: (%s,%s)" % (posn, term, slots[posn]))
            slots[posn] = term
    assert len(slots) == 0 or slots[-1] != '_' # We should only have grown the list to accomidate the terms
    return slots

def dump_term_vects(start_at=0, dump_every=60000, terms_type='document'):
    client = SolrClient()

    q = 'type:%s' % terms_type

    start_cursor = '*'
    if (start_at > 0):
        start_cursor = client.term_vectors_skip_to(q=q, index='msmarco', skip=start_at)

    idx = start_at + 1
    rows = []
    start = datetime.now()
    for doc_id, body_vects in client.term_vectors(q=q, index='msmarco', field='body', start_cursor=start_cursor):

        val = [doc_id] + reorder_term_vectors(body_vects)
        rows.append(val)

        if idx % dump_every == (dump_every - 1):
            with gzip.open('.cache/%s_%s.csv.gz' % (terms_type, idx), 'wt') as f:
                print("Dumping! %s | %s rows" % (idx, len(rows)))
                terms_per_line = csv.writer(f)
                terms_per_line.writerows(rows)
                rows = []
        if idx % 1000 == 0:
            print("Dumped %s Docs Rows: %s -- %s" % (idx, len(rows), (datetime.now() - start) / idx))
        idx += 1
    with gzip.open('.cache/%s_%s.csv.gz' % (terms_type, idx), 'wt') as f:
        print("Dumping! %s | %s rows" % (idx, len(rows)))
        terms_per_line = csv.writer(f)
        terms_per_line.writerows(rows)

if __name__ == "__main__":
    start_at = 0
    from sys import argv
    #print("Dump Indexed Questions")
    #dump_term_vects(start_at=start_at, terms_type='question', dump_every=400000)

    if len(argv) > 1:
        pick_up_from = int(argv[1])
        start_at = pick_up_from + 1
        print("Starting at %s" % start_at)
    dump_term_vects(start_at=start_at)
