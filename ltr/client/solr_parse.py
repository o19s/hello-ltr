"""Solr response parsing utilities.

This module provides functions for parsing Solr's named list format and
converting it to standard Python dictionaries, handling nested structures
and term vector data.
"""

from __future__ import annotations

from typing import Any

from ltr.types import JSONDict


def every_other_zipped(lst: list[Any]) -> zip:
    """Zip every other element of a list into pairs.

    Args:
        lst: List with even number of elements.

    Returns:
        zip: Iterator of tuples pairing elements (0,1), (2,3), (4,5), etc.
    """
    return zip(lst[0::2], lst[1::2])


def dictify(nl_tups: list[tuple[Any, Any]]) -> dict[Any, Any] | list[tuple[Any, Any]]:
    """Convert list of tuples to dictionary if all keys are unique.

    Args:
        nl_tups: List of (key, value) tuples.

    Returns:
        dict or list: Dictionary if all keys are unique, otherwise returns
            the original list of tuples unchanged.
    """
    as_dict = dict(nl_tups)
    if len(as_dict) == len(nl_tups):
        return as_dict
    return nl_tups


def parse_named_list(lst: list[Any]) -> dict[Any, Any] | list[tuple[Any, Any]]:
    """Recursively parse Solr named list format into nested dictionaries.

    Solr named lists are alternating key-value pairs that can be nested.
    This function converts them to standard Python dictionaries.

    Args:
        lst: List in Solr named list format (alternating keys and values).

    Returns:
        dict or list: Parsed dictionary structure, or list of tuples if
            keys are not unique.
    """
    shallow_tups = list(every_other_zipped(lst))

    nl_as_tups = []

    for tup in shallow_tups:
        if isinstance(tup[1], list):
            tup = (tup[0], parse_named_list(tup[1]))
        nl_as_tups.append(tup)
    return dictify(nl_as_tups)


def parse_termvect_namedlist(
    lst: list[Any], field: str
) -> JSONDict | list[tuple[Any, Any]]:
    """Parse Solr term vector named list format with position normalization.

    Parses the named list and performs transformations to create consistent
    JSON structure, specifically normalizing position arrays.

    Args:
        lst: List in Solr named list format containing term vector data.
        field: Field name being parsed.

    Returns:
        dict: Parsed term vector dictionary with normalized structure.
    """

    def listify_posns(posn_attrs: dict[str, int] | list[tuple[str, int]]) -> list[int]:
        """Normalize position attributes to a list format.

        Converts position attributes from various formats (dict or list of tuples)
        into a consistent list of position values.

        Args:
            posn_attrs: Position attributes, either a dict with "position" key
                or a list of (key, value) tuples.

        Returns:
            list: List of position values as integers.
        """
        if isinstance(posn_attrs, dict):
            assert len(posn_attrs) == 1
            return [posn_attrs["position"]]
        return [posn_attr[1] for posn_attr in posn_attrs]

    tv_parsed = parse_named_list(lst)
    if not isinstance(tv_parsed, dict):
        return tv_parsed
    for _doc_id, doc_field_tv in tv_parsed.items():
        if not isinstance(doc_field_tv, dict):
            continue
        for field_name, term_vects in doc_field_tv.items():
            if not isinstance(term_vects, dict):
                continue
            if field_name == field:
                for _term, attrs in term_vects.items():
                    if not isinstance(attrs, dict):
                        continue
                    for attr_key, attr_val in attrs.items():
                        if attr_key == "positions":
                            attrs["positions"] = listify_posns(attr_val)
    return tv_parsed


if __name__ == "__main__":
    solr_nl = [
        "D100000",
        [
            "uniqueKey",
            "D100000",
            "body",
            [
                "1",
                ["positions", ["position", 92, "position", 113]],
                "2",
                ["positions", ["position", 22, "position", 413]],
                "boo",
                [
                    "positions",
                    [
                        "position",
                        22,
                    ],
                ],
            ],
        ],
    ]
    print(repr(parse_termvect_namedlist(solr_nl, "body")))
