import heapq

class Heap:
    # adapted from https://stackoverflow.com/a/8875823/8123
   def __init__(self, initial=None, key=lambda x:x, max_size=1000):
       self.key = key
       self.max_size = max_size
       if initial:
           self._data = [(key(item), item) for item in initial]
           heapq.heapify(self._data)
       else:
           self._data = []

   def push(self, item):
       heapq.heappush(self._data, (self.key(item), item))

   def pop(self):
       return heapq.heappop(self._data)[1]


class Colocations:
    def chi_square(self, term1, term2, min_term_count):
        term2_count = sum([term_stat[1] for term_stat in self.w2_track[term2]])
        term1_count = sum([term_stat[1] for term_stat in self.w1_track[term1]])
        if term1_count < min_term_count:
            return 0
        if term2_count < min_term_count:
            return 0
        term1_w_term2 =  0
        for term_stats in self.w1_track[term1]:
            if term_stats[0] == term2:
                term1_w_term2 = term_stats[1]

        term1_wo_term2 = term1_count - term1_w_term2
        term2_wo_term1 = term2_count - term1_w_term2
        neither_term1_nor_term2 = self.num_bigrams - max(term1_count, term2_count)

        chi_sq_num = self.num_bigrams * ((term1_w_term2 * neither_term1_nor_term2 - term1_wo_term2 * term2_wo_term1)**2)

        col1 = term1_w_term2 + term1_wo_term2
        col2 = term2_wo_term1 + neither_term1_nor_term2
        row1 = term1_w_term2 + term1_wo_term2
        row2 = term2_wo_term1 + neither_term1_nor_term2

        #print("T12 %s T1^2 %s T^12 %s T^1^2 %s" %
        #        (term1_w_term2, term1_wo_term2, term2_wo_term1, neither_term1_nor_term2))

        chi_sq_denom = (col1*col2*row1*row2)

        if chi_sq_denom == 0:
            return 0

        chi_sq = chi_sq_num / chi_sq_denom

        return chi_sq

    def score_all_begins_with(self, term1, min_term_count=20):
        scored_bigrams = Heap(key=lambda x: -x[0])
        for t2, _ in self.w1_track[term1]:
            bg = (self.chi_square(term1,
                                  t2,
                                  min_term_count=min_term_count), term1, t2)
            scored_bigrams.push(bg)
        return scored_bigrams

    def score_all(self,  min_term_count=20):
        scored_bigrams = Heap(key=lambda x: -x[0])
        for term1, term_stats in self.w1_track.items():
            for term2, _ in term_stats:
                bg = (self.chi_square(term1,
                                      term2,
                                      min_term_count=min_term_count), term1, term2)
                scored_bigrams.push(bg)
        return scored_bigrams


    def __init__(self, bigram_index):
        self.bigram_index = bigram_index
        self.gather_bigrams()

    def gather_bigrams(self, min_df=5):
        from collections import defaultdict
        self.w1_track = defaultdict(list)
        self.w2_track = defaultdict(list)
        self.num_bigrams = 0
        for bigram, df in self.bigram_index.bigrams_above_freq(3):
            term1 = bigram[0]; term2 = bigram[1]
            self.num_bigrams += df
            if df >= min_df:
                self.w1_track[term1].append( (term2, df) )
                self.w2_track[term2].append( (term1, df) )
            else:
                pass
                #print("Skipping %s,%s - DF %s" % (term1,term2, df))

if __name__ == "__main__":
    coloc = Colocations()
    scored_bigrams = coloc.score_all(min_term_count=10)
    import pdb; pdb.set_trace()
    for i in range(0,100):
        bg = scored_bigrams.pop()
        print("%s %s %s => %s" % (bg[0], bg[1], bg[2], "%s %s" % (bg[1],bg[2])))

