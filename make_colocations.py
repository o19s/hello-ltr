from ltr.helpers.colocations.bigram_index import BigramIndex
from ltr.helpers.colocations.colocations import Colocations





if __name__ == "__main__":
    from sys import argv

    bigram_index = BigramIndex()

    if argv[1].endswith('/'):
        print("Pulling in Query Bigrams, min_df = 1")
        bigram_index_questions = BigramIndex.from_folder(argv[1], prefix='question', min_df=1)

        print("Pulling in Doc Bigrams, min_df = 2")
        bigram_index_docs = BigramIndex.from_folder(argv[1], prefix='document', min_df=2)

        bigram_index.merge(bigram_index_questions)
        bigram_index.merge(bigram_index_docs)


        bigram_index.dump('.cache/questions_and_doc.bigrams.pkl.gz')


    else:

        bigram_index = BigramIndex.from_pkl_gz(argv[1])


    for term1, term2, tf in bigram_index.common_n_bigrams(50):
        print(term1, term2, tf)

    coloc = Colocations(bigram_index=bigram_index)
    print("Scoring %s Bigrams" % len(bigram_index))
    import pdb; pdb.set_trace()
    scored_bigrams = coloc.score_all_begins_with(term1=argv[2], min_term_count=1)
    try:
        while True:
            bg = scored_bigrams.pop()
            print("%s %s %s" % (bg[1], bg[2], bg[0]))
            #f.write("%s %s => %s # %s\n" % (bg[1], bg[2], "%s_%s" % (bg[1],bg[2]), bg[0]))
    except IndexError:
        pass

