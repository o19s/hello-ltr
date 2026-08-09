"""Typo injection for testing fuzzy search capabilities.

This module provides functionality for injecting random typos into judgment
files to test how well search systems handle misspellings and typos.
"""

try:
    from helpers.butterfingers import butterfingers
    from helpers.logger import get_logger  # type: ignore[import-untyped]
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
    from .logger import get_logger

logger = get_logger(__name__)


def typo_it(judgment_in_file: str, judgment_out_file: str, rounds: int = 100) -> None:
    """Inject random typos into judgment keywords to create test data.

    Reads judgments from a file, generates typo variants of keywords using
    the butterfingers algorithm, and creates new query-judgment pairs with
    the typo variants. This is useful for testing fuzzy search capabilities.

    Args:
        judgment_in_file: Path to input judgment file.
        judgment_out_file: Path to output file where judgments with typos will be written.
        rounds: Number of rounds of typo generation to attempt (default: 100).
            Each round attempts to generate a typo for each unique query keyword.

    Returns:
        None: Results are written to judgment_out_file.

    Note:
        Duplicate typos are skipped. Each typo variant gets a new query ID.
        The original judgments are preserved, with new typo-based judgments appended.
    """
    with open(judgment_in_file) as f:
        curr_judgments = list(judgments_from_file(f))
    if not curr_judgments:
        raise ValueError(f"No judgments found in {judgment_in_file}")
    last_qid = curr_judgments[-1].qid
    judg_dict = judgments_by_qid(curr_judgments)

    existing_typos = set()

    for _ in range(rounds):
        for judglist in judg_dict.values():
            keywords = judglist[0].keywords
            keywords_w_typo = butterfingers(keywords)

            if keywords_w_typo != keywords and keywords_w_typo not in existing_typos:
                new_qid = last_qid + 1
                logger.info(f"{keywords} => {keywords_w_typo}")
                last_qid += 1
                for judg in judglist:
                    typo_judg = Judgment(
                        grade=judg.grade,
                        qid=new_qid,
                        keywords=keywords_w_typo,
                        doc_id=judg.docId,
                    )
                    curr_judgments.append(typo_judg)
                existing_typos.add(keywords_w_typo)

    with open(judgment_out_file, "w") as f:
        judgments_to_file(f, judgments_list=curr_judgments)


if __name__ == "__main__":
    typo_it(
        judgment_in_file="title_judgments.txt",
        judgment_out_file="title_fuzzy_judgments.txt",
    )

    # Clone a judgment, inject random typos
