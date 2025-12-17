import json

from elasticsearch import Elasticsearch, TransportError

from ltr.helpers.es_url_parse import parse_url
from ltr.judgments import (
    Judgment,
    judgments_by_qid,
    judgments_from_file,
    judgments_to_file,
)


def format_search(keywords):
    """Format a search query using the rateSearch.json.jinja template.

    Args:
        keywords: Search keywords string.

    Returns:
        dict: Elasticsearch query dictionary parsed from rendered template.
    """
    from jinja2 import Template

    with open("rateSearch.json.jinja") as f:
        template = Template(f.read())
    json_str = template.render(keywords=keywords)
    return json.loads(json_str)


def format_fuzzy(keywords):
    """Format a fuzzy search query using the rateFuzzySearch.json.jinja template.

    Args:
        keywords: Search keywords string.

    Returns:
        dict: Elasticsearch fuzzy query dictionary parsed from rendered template.
    """
    from jinja2 import Template

    with open("rateFuzzySearch.json.jinja") as f:
        template = Template(f.read())
    json_str = template.render(keywords=keywords)
    return json.loads(json_str)


def get_potential_results(es_url, keywords, fuzzy):
    """Execute a search query against Elasticsearch and return results.

    Args:
        es_url: Elasticsearch URL in format "http://host:port/index/".
        keywords: Search keywords string.
        fuzzy: If True, use fuzzy search format; otherwise use regular search format.

    Returns:
        list: List of search result hits from Elasticsearch.

    Raises:
        TransportError: If the Elasticsearch query fails.
    """
    (es_url, index, _search_type) = parse_url(es_url)
    es = Elasticsearch(es_url)

    query = format_fuzzy(keywords) if fuzzy else format_search(keywords)
    try:
        print(f"Query {json.dumps(query)}")
        results = es.search(index=index, body=query)
        return results["hits"]["hits"]
    except TransportError as e:
        print(f"Query {json.dumps(query)}")
        print(f"Query Error: {e.error} ")
        print(f"More Info  : {e.info} ")
        raise e


def grade_results(results, keywords, qid):
    """Interactively grade search results by prompting user for relevance ratings.

    Displays each result's title, release year, vote count, and overview,
    then prompts the user to rate it on a scale of 0-4.

    Args:
        results: List of Elasticsearch search result hits.
        keywords: Search keywords string (used for creating Judgment objects).
        qid: Query ID for the judgments.

    Returns:
        list: List of Judgment objects with user-provided grades.
    """
    title_field = "title"
    overview_field = "overview"
    release_date = "release_year"
    vote_count = "vote_count"
    ratings = []
    print(f"Rating {len(results)} results")
    for result in results:
        grade = None
        if "fields" not in result and "_source" in result:
            result["fields"] = result["_source"]
        if "fields" in result:
            print("")
            print("")
            print(f"## {result['fields'][title_field]} {result['_id']} ")
            print("")
            print(f" Release Year  {result['fields'][release_date]} ")
            print("")
            print(f" Votes  {result['fields'][vote_count]} ")
            print("")
            print(f"   {result['fields'][overview_field]} ")
            print("")
            # print("     %s " % (" ".join([cast['name'] for cast in result['fields']['cast']])))
            while grade not in ["0", "1", "2", "3", "4"]:
                grade = input("Rate this shiznit (0-4) ")
            judgment = Judgment(
                int(grade), qid=qid, keywords=keywords, doc_id=result["_id"]
            )
            ratings.append(judgment)

    return ratings


def load_judgments(judg_file):
    """Load judgments from a file and return statistics.

    Args:
        judg_file: Path to the judgments file.

    Returns:
        tuple: A tuple containing:
            - curr_judgments: List of Judgment objects loaded from file.
            - existing_kws: Set of keyword strings already in the file.
            - last_qid: Highest query ID found in the file (0 if file doesn't exist).
    """
    curr_judgments = []
    existing_kws = set()
    last_qid = 0
    try:
        with open(judg_file) as f:
            curr_judgments = list(judgments_from_file(f))
            existing_kws = {judg.keywords for judg in curr_judgments}
            judg_dict = judgments_by_qid(curr_judgments)
            judg_profile = []
            for _qid, judglist in judg_dict.items():
                judg_profile.append((judglist[0], len(judglist)))
            judg_profile.sort(key=lambda j: j[1], reverse=True)
            for prof in judg_profile:
                print(f"{prof[0].keywords} has {prof[1]} judgments")

            last_qid = curr_judgments[-1].qid
    except FileNotFoundError:
        pass

    return (curr_judgments, existing_kws, last_qid)


def seeded_judgments_from(curr_judgments, existing_kws, keywords):
    """Find existing judgments for given keywords.

    Args:
        curr_judgments: List of current Judgment objects.
        existing_kws: Set of keyword strings that already have judgments.
        keywords: Keywords to search for.

    Returns:
        tuple: A tuple containing:
            - seeded_judgments: List of Judgment objects matching the keywords.
            - existing_qid: Query ID if found, otherwise -1.
    """
    existing_qid = -1
    seeded_judgments = []
    if keywords in existing_kws:
        for judgment in curr_judgments:
            if judgment.keywords == keywords:
                seeded_judgments.append(judgment)
                existing_qid = judgment.qid
    return seeded_judgments, existing_qid


def handle_keywords(input_kws, existing_kws, curr_judgments):
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

    keywords_with_expansion = input_kws.split(";")
    keywords_with_butterfingers = input_kws.split("!")
    keywords_with_search_instead = input_kws.split(";;")
    keywords_with_copy = input_kws.split("<-")
    keywords = keywords_with_expansion[0]
    search_with = keywords
    fuzzy = False
    copy_src_keywords = None
    if len(keywords_with_copy) > 1:
        keywords = keywords_with_copy[0]
        copy_src_keywords = keywords_with_copy[1]
    if len(keywords_with_expansion) > 1:
        search_with += f" {keywords_with_expansion[1]}"
    if len(keywords_with_search_instead) > 1:
        search_with = keywords_with_search_instead[1]
    if len(keywords_with_butterfingers) > 1:
        keywords = keywords_with_butterfingers[0]
        search_with = butterfingers(keywords, prob=0.2)
        fuzzy = True

    if copy_src_keywords is not None:
        this_query_judgments, existing_qid = seeded_judgments_from(
            curr_judgments, existing_kws, copy_src_keywords
        )
    else:
        this_query_judgments, existing_qid = seeded_judgments_from(
            curr_judgments, existing_kws, keywords
        )

    return (
        keywords,
        search_with,
        this_query_judgments,
        existing_qid,
        fuzzy,
        copy_src_keywords,
    )


def fold_in_new_ratings(full_judgments, orig_judgments, new_judgs):
    """Merge new judgments into existing judgments, updating grades for matching pairs.

    For each new judgment, if a matching judgment exists (same query and document),
    update its grade. Otherwise, append the new judgment to the full list.

    Args:
        full_judgments: List of all Judgment objects (will be modified).
        orig_judgments: List of original Judgment objects for the query.
        new_judgs: List of new Judgment objects to merge in.
    """
    for new_judg in new_judgs:
        was_an_update = False
        for orig_judg in orig_judgments:
            if orig_judg.same_query_and_doc(new_judg):
                orig_judg.grade = new_judg.grade
                was_an_update = True
        if not was_an_update:
            full_judgments.append(new_judg)


def rate_results():
    """Main interactive function for rating search results and building judgments.

    Prompts the user for keywords, searches Elasticsearch, displays results,
    collects relevance ratings, and saves judgments to a file. Supports various
    input formats for query expansion, fuzzy search, and copying judgments.

    The function runs in a loop until the user enters "GTFO" or empty input.
    All judgments are saved to the file specified in sys.argv[1].
    """
    from sys import argv

    es_url = "http://localhost:9200/tmdb/"

    judg_file = argv[1]
    full_judgments, existing_kws, last_qid = load_judgments(judg_file)

    keywords = "-"
    new_qid = last_qid + 1
    while len(keywords) > 0:
        input_kws = input("Enter the Keywords ('GTFO' to exit) ")

        if input_kws == "GTFO":
            break

        (
            keywords,
            search_with,
            orig_query_judgments,
            existing_qid,
            fuzzy,
            copy_src_kws,
        ) = handle_keywords(input_kws, existing_kws, full_judgments)
        curr_qid = 0
        if existing_qid > 0:
            curr_qid = existing_qid
            print(f"Updating judgments for qid:{curr_qid}")
        else:
            existing_kws.add(keywords)
            curr_qid = new_qid
            print(f"New Keywords {keywords} qid:{curr_qid}")
            new_qid += 1

        new_query_judgments = []
        if copy_src_kws is not None:
            print(f"Copying from {keywords} <- {copy_src_kws}")
            for judg in orig_query_judgments:
                judgment = Judgment(
                    int(judg.grade), qid=new_qid, keywords=keywords, doc_id=judg.docId
                )
                new_query_judgments.append(judgment)
            existing_kws.add(keywords)
            curr_qid = new_qid
            new_qid += 1
        else:
            results = get_potential_results(es_url, search_with, fuzzy)
            new_query_judgments = grade_results(results, keywords, curr_qid)

        fold_in_new_ratings(full_judgments, orig_query_judgments, new_query_judgments)

    with open(judg_file, "w") as f:
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
