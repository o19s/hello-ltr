from collections import Counter
import pickle

def bigrams(terms):
    """ Every item in a list with it's next item """
    return zip(terms, terms[1:])

class TermDict:

    def __init__(self):
        self.term_to_ord = {}
        self.ord_to_term = []

    def term_ord(self, term):

        try:
            term_ord = self.term_to_ord[term]
            return term_ord
        except KeyError:
            term_ord = len(self.ord_to_term)
            self.ord_to_term.append(term)
            self.term_to_ord[term] = term_ord
            return term_ord

    def term(self, term_ord):
        return self.ord_to_term[term_ord]


class BigramIndex:

    def __init__(self, docfreq=True):
        self.bigram_dict_ttf = Counter() #total tf over all docs of each bigram, keyed by term ord
        self.bigram_dict_df = Counter() # doc freq over all docs of each bigram, keyed by term ord
        self.docfreq = docfreq
        self.term_dict = TermDict()

    def add_doc(self, terms):
        bigrammed = [b for b in bigrams([self.term_dict.term_ord(term) for term in terms])]
        for bigram in bigrammed:
            self.bigram_dict_ttf[bigram] += 1
        for bigram in set(bigrammed):
            self.bigram_dict_df[bigram] += 1

    def common_n_bigrams(self, n):
        for bigram, count in self.bigram_dict_df.most_common(n):
            yield bigram[0], bigram[1], count

    def bigrams_above_freq(self, freq):
        for bigram, count in self.bigram_dict_df.most_common():
            if count > freq:
                yield bigram[0], bigram[1], count

    def dump(self, fname):
        with open(fname, 'wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def from_pkl(fname):
        with open(fname, 'rb') as f:
            return pickle.load(f)


