"""Typo injection for testing fuzzy search capabilities.

This module provides functionality for injecting random typos into judgment
files to test how well search systems handle misspellings and typos.
"""

try:
    from helpers.butterfingers import butterfingers
    from judgments import (
        Judgment,
        judgments_by_qid,
        judgments_from_file,
        judgments_to_file,
    )
except ImportError:
    from .helpers.butterfingers import butterfingers
    from .judgments import (
        Judgment,
        judgments_by_qid,
        judgments_from_file,
        judgments_to_file,
    )


def typoIt(judgmentInFile, judgmentOutFile, rounds=100):
    """Inject random typos into judgment keywords to create test data.

    Reads judgments from a file, generates typo variants of keywords using
    the butterfingers algorithm, and creates new query-judgment pairs with
    the typo variants. This is useful for testing fuzzy search capabilities.

    Args:
        judgmentInFile: Path to input judgment file.
        judgmentOutFile: Path to output file where judgments with typos will be written.
        rounds: Number of rounds of typo generation to attempt (default: 100).
            Each round attempts to generate a typo for each unique query keyword.

    Returns:
        None: Results are written to judgmentOutFile.

    Note:
        Duplicate typos are skipped. Each typo variant gets a new query ID.
        The original judgments are preserved, with new typo-based judgments appended.
    """
    with open(judgmentInFile) as f:
        currJudgments = list(judgments_from_file(f))
    lastQid = currJudgments[-1].qid
    judgDict = judgments_by_qid(currJudgments)

    existingTypos = set()

    for _ in range(rounds):
        for judglist in judgDict.values():
            keywords = judglist[0].keywords
            keywordsWTypo = butterfingers(keywords)

            if keywordsWTypo != keywords and keywordsWTypo not in existingTypos:
                newQid = lastQid + 1
                print(f"{keywords} => {keywordsWTypo}")
                lastQid += 1
                for judg in judglist:
                    typoJudg = Judgment(
                        grade=judg.grade,
                        qid=newQid,
                        keywords=keywordsWTypo,
                        docId=judg.docId,
                    )
                    currJudgments.append(typoJudg)
                existingTypos.add(keywordsWTypo)

    with open(judgmentOutFile, "w") as f:
        judgments_to_file(f, judgmentsList=currJudgments)


if __name__ == "__main__":
    typoIt(
        judgmentInFile="title_judgments.txt",
        judgmentOutFile="title_fuzzy_judgments.txt",
    )

    # Clone a judgment, inject random typos
