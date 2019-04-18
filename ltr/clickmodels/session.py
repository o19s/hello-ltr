
class Doc:
    def __init__(self, click, doc_id, click_val):
        self.click = click
        self.doc_id = doc_id
        self.click_val = click_val

    def __repr__(self):
        return "Doc(doc_id=%s, click=%s, click_val=%s)" % (self.doc_id, self.click, self.click_val)

    def __str__(self):
        return "(%s, %s, %s)" % (self.doc_id, self.click, self.click_val)


class Session:
    def __init__(self, query, docs):
        self.query = query
        self.docs = docs

    def __repr__(self):
        return "Session(query=%s, docs=%s)" % (self.query, self.docs)

    def __str__(self):
        return "(%s, (%s))" % (self.query, self.docs)


def build_one(sess_tuple):
    """ Take a tuple where
        0th item is query (a string that uniquely identifies it)
        1st item is a list of docs, with clicks
                 and optionally a click_val


        ('A', ((1, True), (2, False), (3, True), (0, False))),

        alternatively a value can be attached to the doc

        ('A', ((1, True, 0.9), (2, False, 0.8), (3, True, 1.0), (0, False))),
    """
    query = sess_tuple[0]
    docs = []
    for doc_tuple in sess_tuple[1]:
        click_val=1.0
        if len(doc_tuple) > 2:
            click_val = doc_tuple[2]
        docs.append(Doc(doc_id=doc_tuple[0],
                        click=doc_tuple[1],
                        click_val=click_val))
    return Session(query=query, docs=docs)


def build(sess_tuples):
    sesss = []
    for sess_tup in sess_tuples:
        sesss.append(build_one(sess_tup))
    return sesss

