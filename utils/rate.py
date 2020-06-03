import utils
from ltr.helpers.esUrlParse import parseUrl
from ltr.judgments import Judgment, judgments_from_file, judgments_to_file, judgments_by_qid
from elasticsearch import Elasticsearch, TransportError
import json

def format_search(keywords):
    from jinja2 import Template
    template = Template(open("rateSearch.json.jinja").read())
    jsonStr = template.render(keywords=keywords)
    return json.loads(jsonStr)

def format_fuzzy(keywords):
    from jinja2 import Template
    template = Template(open("rateFuzzySearch.json.jinja").read())
    jsonStr = template.render(keywords=keywords)
    return json.loads(jsonStr)

def get_potential_results(es_url, keywords, fuzzy):
    (es_url, index, search_type) = parseUrl(es_url)
    es = Elasticsearch(es_url)

    if fuzzy:
        query = format_fuzzy(keywords)
    else:
        query = format_search(keywords)
    try:
        print("Query %s" % json.dumps(query))
        results = es.search(index=index, body=query)
        return results['hits']['hits']
    except TransportError as e:
        print("Query %s" % json.dumps(query))
        print("Query Error: %s " % e.error)
        print("More Info  : %s " % e.info)
        raise e



def grade_results(results, keywords, qid):
    title_field = 'title'
    overview_field = 'overview'
    release_date = 'release_year'
    vote_count = 'vote_count'
    ratings = []
    print("Rating %s results" % len(results))
    for result in results:
        grade = None
        if 'fields' not in result:
            if '_source' in result:
                result['fields'] = result['_source']
        if 'fields' in result:
            print("")
            print("")
            print("## %s %s " % (result['fields'][title_field], result['_id']))
            print("")
            print(" Release Year  %s " % result['fields'][release_date])
            print("")
            print(" Votes  %s " % result['fields'][vote_count])
            print("")
            print("   %s " % result['fields'][overview_field])
            print("")
            #print("     %s " % (" ".join([cast['name'] for cast in result['fields']['cast']])))
            while grade not in ["0", "1", "2", "3", "4"]:
                grade = input("Rate this shiznit (0-4) ")
            judgment = Judgment(int(grade), qid=qid, keywords=keywords, docId=result['_id'])
            ratings.append(judgment)

    return ratings


def load_judgments(judg_file):
    currJudgments = []
    existingKws = set()
    last_qid = 0
    try:
        with open(judg_file) as f:
            currJudgments = [judg for judg in judgments_from_file(f)]
            existingKws = set([judg.keywords for judg in currJudgments])
            judgDict = judgments_by_qid(currJudgments)
            judgProfile = []
            for qid, judglist in judgDict.items():
                judgProfile.append((judglist[0], len(judglist)))
            judgProfile.sort(key=lambda j: j[1], reverse=True)
            for prof in judgProfile:
                print("%s has %s judgments" % (prof[0].keywords, prof[1]))

            last_qid = currJudgments[-1].qid
    except FileNotFoundError:
        pass

    return (currJudgments, existingKws, last_qid)


def seeded_judgments_from(currJudgments, existing_kws, keywords):
    existingQid = -1
    seeded_judgments = []
    if keywords in existing_kws:
        for judgment in currJudgments:
            if judgment.keywords == keywords:
                seeded_judgments.append(judgment)
                existingQid = judgment.qid
    return seeded_judgments, existingQid


def handleKeywords(inputKws, existing_kws, currJudgments):
    """
    Handles the users input at the prompt, returns tuple describing
    the requested action
    - keywords: what is being graded
    - search_with: the search to execute to grade results
    - this_query_judgments: if the query has been graded already
    - existing_qid: the query id (if any) if the query already exists
    - fuzzy: whether to execute a fuzzy search when grading
    - copy_src_keywords: whether we're copying one set of judgments into another,
                         this will be set to the src keywords to copy from
                         (ie copy 'oceans 11' grades into 'oceans eleven')
    """

    from ltr.helpers.butterfingers import butterfingers

    keywordsWithExpansion = inputKws.split(';')
    keywordsWithButterfingers = inputKws.split('!')
    keywordsWithSearchInstead = inputKws.split(';;')
    keywordsWithCopy = inputKws.split('<-')
    keywords = keywordsWithExpansion[0]
    searchWith = keywords
    fuzzy = False
    copy_src_keywords = None
    if (len(keywordsWithCopy) > 1):
        keywords = keywordsWithCopy[0]
        copy_src_keywords = keywordsWithCopy[1]
    if (len(keywordsWithExpansion) > 1):
        searchWith += " %s" % keywordsWithExpansion[1]
    if (len(keywordsWithSearchInstead) > 1):
        searchWith = keywordsWithSearchInstead[1]
    if (len(keywordsWithButterfingers) > 1):
        keywords = keywordsWithButterfingers[0]
        searchWith = butterfingers(keywords, prob=0.2)
        fuzzy = True


    if copy_src_keywords is not None:
        this_query_judgments, existing_qid = seeded_judgments_from(currJudgments, existing_kws, copy_src_keywords)
    else:
        this_query_judgments, existing_qid = seeded_judgments_from(currJudgments, existing_kws, keywords)

    return keywords, searchWith, this_query_judgments, existing_qid, fuzzy, copy_src_keywords


def foldInNewRatings(fullJudgments, origJudgments, newJudgs):
    for newJudg in newJudgs:
        wasAnUpdate = False
        for origJudg in origJudgments:
            if (origJudg.sameQueryAndDoc(newJudg)):
                origJudg.grade = newJudg.grade
                wasAnUpdate = True
        if not wasAnUpdate:
            fullJudgments.append(newJudg)



def rate_results():
    from sys import argv

    esUrl = 'http://localhost:9200/tmdb/'

    judgFile = argv[1]
    full_judgments, existing_kws, last_qid = load_judgments(judgFile)

    keywords = "-"
    new_qid = last_qid + 1
    while len(keywords) > 0:
        input_kws = input("Enter the Keywords ('GTFO' to exit) ")

        if input_kws == "GTFO":
            break

        keywords, search_with, orig_query_judgments, existing_qid, fuzzy, copy_src_kws =\
                handleKeywords(input_kws, existing_kws, full_judgments)
        curr_qid = 0
        if existing_qid > 0:
            curr_qid = existing_qid
            print("Updating judgments for qid:%s" % curr_qid)
        else:
            existing_kws.add(keywords)
            curr_qid = new_qid
            print("New Keywords %s qid:%s" % (keywords, curr_qid))
            new_qid += 1

        new_query_judgments = []
        if copy_src_kws is not None:
            print("Copying from %s <- %s" % (keywords, copy_src_kws))
            for judg in orig_query_judgments:
                judgment = Judgment(int(judg.grade), qid=new_qid, keywords=keywords, docId=judg.docId)
                new_query_judgments.append(judgment)
            existing_kws.add(keywords)
            curr_qid = new_qid
            new_qid += 1
        else:
            results = get_potential_results(esUrl, search_with, fuzzy)
            new_query_judgments = grade_results(results, keywords, curr_qid)

        foldInNewRatings(full_judgments, orig_query_judgments, new_query_judgments)

    with open(judgFile, 'w') as f:
        judgments_to_file(f, full_judgments)




if __name__ == "__main__":
    """
        Prompts console user for judgments
        Usage python rate.py ratingsFileName

        Prompt guide
            foo -- searches for "foo" using rateSearch.json.jinja,
            foo; bar -- rate keyword "foo", but add "bar" to the query
            foo;; bar -- rate keyword "foo", searching for "bar" instead
            foo!bf bar -- rate keyword "foo", performing a fuzzy search on foo

    """
    rate_results()
