# Search for Developers

## Overview

This document attempts to provide an introduction to various concepts and methods developers may not have encountered previously.

## Corpus

A corpus, for our purposes, is a collection of entities. For example, a corpus might include a large portion of the internet including documents, videos, audio clips, and applications. Another corpus might consist of documents related to various legal entities (e.g., corporations).

The corpus is the sum total of the material we will be searching against.

### Further Reading
- USC Libraries Research Guides. [What is a "Corpus"?](https://libguides.usc.edu/Corpora). 2025.



## Judgment Lists

When attempting to determine whether a search query is returning high quality results one can use a judgment list.

In a judgment list we have three essential columns:

1. A query, e.g. "household plants"
    - Each judgment list can include a wide variety of queries and the grade for each possible result will vary based on the query.
2. A possible result, e.g. "trip to mars" or "plants to grow in your house"
    - In this case we can see that the latter result is much more relevant than the former for this particular query ("household plants").
3. A grade, e.g. 1, 2, 3, or 4.
    - The numbers we use are relative to each other. We could use binary (0, 1), integers (1, 2, 3, 4), or floats (e.g. 0.15, 0.89).
    - Our scale could be 1 is lowest to 4 is highest or vice versa - 4 is highest, 1 is lowest.

These judgment lists can be created in a variety of ways, for example:
1. Human rankers manually curate possible results.
2. Using LLMs as Judges to rank the relevance of possible results.
3. Using implicit judgments based on user data (e.g. how many times does someone search for X click on result Y compared to result Z?)

### Further Reading
- Doug Turnbull. [What is a Judgment List?](https://softwaredoug.com/blog/2021/02/21/what-is-a-judgment-list). 2021.