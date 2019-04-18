

ranks = [0.4, 0.2, 0.1, 0.95]

# For two queries, the doc attractiveness for docs 1-10
queryA = {1: 0.0,
          2: 0.0,
          3: 0.0,
          4: 0.0,
          5: 0.0,
          6: 0.0,
          7: 0.0,
          8: 0.0,
          9: 0.0,
          0: 0.0}

from copy import copy
queryB = copy(queryA)

queries = {}
queries['A'] = queryA
queries['B'] = queryB

# Query => [(docid, click?)...]
sessions = [
  ('A', ((1, True), (2, False), (3, True), (0, False))),
  ('B', ((5, False), (2, True), (3, True), (0, False))),
  ('A', ((1, False), (2, False), (3, True), (0, False))),
  ('B', ((1, False), (2, False), (3, False), (9, True))),
  ('A', ((9, False), (2, False), (1, True), (0, True))),
  ('B', ((6, True), (2, False), (3, True), (1, False))),
  ('A', ((7, False), (4, True), (1, False), (3, False))),
  ('B', ((8, True), (2, False), (3, True), (1, False))),
  ('A', ((1, False), (4, True), (2, False), (3, False))),
  ('B', ((7, True), (4, False), (5, True), (1, True))),
]


def session_has_query_doc(session, query_id, doc_id):
    has_query = session[0] == query_id
    if has_query:
        for doc in session[1]:
            if doc[0] == doc_id:
                return True
    return False

def doc_click_info(session, doc_id):
    for rank, doc in enumerate(session[1]):
        if doc[0] == doc_id:
           return rank, doc[1]
    return False


def add_attractiveness(a_by_query_doc, query_id, doc_id, a):
    if query_id not in a_by_query_doc:
        a_by_query_doc[query_id] = {}
    if doc_id not in a_by_query_doc[query_id]:
        a_by_query_doc[query_id][doc_id] = [0,0]
    a_by_query_doc[query_id][doc_id][0] += 1
    a_by_query_doc[query_id][doc_id][1] += a


def update_attractiveness(sessions, queries):
    attractions = {}
    num_sessions = {}
    for session in sessions:
        query_id = session[0]
        docs = session[1]
        for rank, (doc_id, click) in enumerate(docs):
            att = 0
            if click:
                # By PBM rules, if its clicked,
                # the user thought it was attractive
                att = 1
            else:
                exam = ranks[rank]
                assert exam <= 1.0
                if exam > 1:
                    import pdb; pdb.set_trace()
                doc_a = queries[query_id][doc_id]
                # Not examined, but attractive /
                # 1 - (examined and attractive)
                # When not clicked:
                #  If somehow this is currently a rank examined
                #  a lot and this doc is historically attractive, then
                #  we might still count it as mostly attractive
                # OR if the doc IS examined a lot AND its not
                #  attractive, then we do the opposite, add
                #  close to 0
                att = (((1 - exam) * doc_a) / (1 - (exam * doc_a)))

            # Store away a_sum and
            query_doc_key = (query_id, doc_id)
            if query_doc_key not in attractions:
                attractions[query_doc_key] = 0
                num_sessions[query_doc_key] = 0
            assert att <= 1.0
            attractions[query_doc_key] += att
            num_sessions[query_doc_key] += 1
            assert attractions[query_doc_key] <= num_sessions[query_doc_key]

    # Update the main query attractiveness from the attractions / num sessions
    for (query_id, doc_id), a_sum in attractions.items():
        query_doc_key = (query_id, doc_id)
        att = a_sum / num_sessions[query_doc_key]
        assert att <= 1.0
        if query_id not in queries:
            queries[query_id] = {}
        if doc_id not in queries[query_id]:
            queries[query_id][doc_id] = 0
        queries[query_id][doc_id] = att

def update_examines(sessions, queries, ranks):
    new_rank_probs = [0,0,0,0]

    for session in sessions:
        query_id = session[0]
        for rank, (doc_id, click) in enumerate(session[1]):
            if click:
                new_rank_probs[rank] += 1
            else:
                # attractiveness at this query/doc pair
                a_qd = queries[query_id][doc_id]
                numerator = (1 - a_qd) * ranks[rank]
                denominator = 1 - (a_qd * ranks[rank])
                # When not clicked - was it examined? We have to guess!
                #  - If it has seemed very attractive, we assume it
                #    was not examined. Because who could pass up such
                #    a yummy looking search result? (numerator)
                #
                #  - If its not attractive, but this rank gets examined
                #    a lot, the new rank prob is closer to 1
                #    (approaches ranks[rank] / ranks[rank])
                #
                #  - If its not examined much, wont contribute much
                new_rank_probs[rank] += numerator / denominator
    for i in range(len(new_rank_probs)):
        ranks[i] = new_rank_probs[i] / len(sessions)


def position_based_model(sessions, queries, ranks, rounds=20):
    """ Given the observed sessions
        Initialized:
          - prob a ranks is examined (`ranks`)
          - randomly initialized query/doc attractiveness

        Compute:
          - Probability a doc is attractive for a query
    """
    for i in range(0,rounds):
        update_attractiveness(sessions, queries)
        update_examines(sessions, queries, ranks)
        print(ranks)
        print(queries['A'][1])
        print(queries['B'][1])


def cascading_model(sessions, queries):
    """ Cascading model can be solved directly:
         - sessions with skips count against a doc
         - sessions with clicks count for
         - stop at first click
        """
    session_counts = {}
    click_counts = {}

    for session in sessions:
        query_id = session[0]
        for rank, (doc_id, click) in enumerate(session[1]):
            query_doc_key = (query_id, doc_id)
            if query_doc_key not in session_counts:
                session_counts[query_doc_key] = 0
                click_counts[query_doc_key] = 0
            session_counts[query_doc_key] += 1

            if click:
                click_counts[query_doc_key] += 1
                break;

    for (query_id, doc_id), count in session_counts.items():
        query_doc_key = (query_id, doc_id)
        queries[query_id][doc_id] = click_counts[query_doc_key] / session_counts[query_doc_key]



if __name__ == "__main__":
    position_based_model(sessions, queries, ranks, rounds=5)

    #cascading_model(sessions, queries)




