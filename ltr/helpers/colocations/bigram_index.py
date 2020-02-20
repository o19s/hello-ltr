from collections import Counter
import pickle
import gzip

def bigrams(terms):
    """ Every item in a list with it's next item """
    return zip(terms, terms[1:])

#class TermDict:
#
#    def __init__(self):
#        #self.term_to_ord = BinarySearchTable()
#        self.hash_to_term = {}
#
#    def term_hash(self, term):
#        str_hash = hash_str(term)
#        self.hash_to_term[str_hash] = term
#        return str_hash
#
#    def term(self, term_hash):
#        return self.hash_to_term[term_hash]


class BigramIndex:

    def __init__(self):
        self.bigram_dict_df = Counter() # doc freq over all docs of each bigram, keyed by term ord

    def add_doc(self, terms):
        bigrammed = [b for b in bigrams(terms)]
        for bigram in set(bigrammed):
            self.bigram_dict_df[bigram] += 1

    def common_n_bigrams(self, n):
        for bigram, count in self.bigram_dict_df.most_common(n):
            yield bigram[0], bigram[1], count

    def bigrams_above_freq(self, freq):
        for bigram, count in self.bigram_dict_df.most_common():
            if count > freq:
                yield bigram, count

    def dump(self, fname):
        with gzip.open(fname, 'wb') as f:
            pickle.dump(self, f)

    def merge(self, other_bg_idx):
        self.bigram_dict_df.update(other_bg_idx.bigram_dict_df)

    def __len__(self):
        return len(self.bigram_dict_df)

    @staticmethod
    def from_pkl_gz(fname):
        with gzip.open(fname, 'rb') as f:
            return pickle.load(f)

    @staticmethod
    def from_folder(folder, prefix='', min_df=1):
        import os

        def all_pkls_in_folder(folder, prefix):
            for filename in os.listdir(folder):
                if filename.endswith('_bigrams_pkl.gz') and filename.startswith(prefix):
                    yield os.path.join(folder, filename)

        bigram_idx = BigramIndex()
        for bigram_pkl_fname in all_pkls_in_folder(folder, prefix):
            print("Adding %s" % bigram_pkl_fname)
            this_bg_idx = BigramIndex.from_pkl_gz(bigram_pkl_fname)

            print("Bigrams Loaded %s" % len(this_bg_idx))

            filtered_bg_idx = BigramIndex()
            for bigram, df in this_bg_idx.bigrams_above_freq(freq=min_df-1):
                filtered_bg_idx.bigram_dict_df[bigram] = df

            print("Bigrams Above DF=%s - %s" % (min_df, len(filtered_bg_idx)))

            bigram_idx.merge(filtered_bg_idx)

        return bigram_idx

