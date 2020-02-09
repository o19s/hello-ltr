from ltr.helpers.colocations.bigram_index import BigramIndex
from ltr.helpers.colocations.colocations import Colocations





if __name__ == "__main__":
    from sys import argv
    bigram_index = BigramIndex.from_pkl(argv[1])

    def t(term_ord):
        return bigram_index.term_dict.ord_to_term[term_ord]

    for term1, term2, tf in bigram_index.common_n_bigrams(50):
        print(t(term1), t(term2), tf)

    coloc = Colocations(bigram_index)
    scored_bigrams = coloc.score_all(min_term_count=10)
    with open('colocs.txt', 'w') as f:
        for i in range(0,10000):
            bg = scored_bigrams.pop()
            f.write("%s %s => %s # %s\n" % (t(bg[1]), t(bg[2]), "%s_%s" % (t(bg[1]),t(bg[2])), bg[0]))


