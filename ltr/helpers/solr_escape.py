"""Solr query syntax escaping utilities.

This module provides functions for escaping special characters in Solr queries
to prevent them from being interpreted as query operators.
"""


def esc_kw(kw):
    """Escape special Solr query syntax characters in a keyword string.

    Escapes characters that have special meaning in Solr query syntax to ensure
    they are treated as literal characters rather than query operators.

    Args:
        kw: Keyword string to escape.

    Returns:
        str: Escaped keyword string with special characters backslash-escaped.

    Note:
        Backslashes are escaped first to prevent double-escaping of other characters.
        The following characters are escaped: \\ ( ) + - : / ] [ * ? { } ~
    """
    kw = kw.replace("\\", "\\\\")  # be sure to do this first, as we inject \!
    kw = kw.replace("(", r"\(")
    kw = kw.replace(")", r"\)")
    kw = kw.replace("+", r"\+")
    kw = kw.replace("-", r"\-")
    kw = kw.replace(":", r"\:")
    kw = kw.replace("/", r"\/")
    kw = kw.replace("]", r"\]")
    kw = kw.replace("[", r"\[")
    kw = kw.replace("*", r"\*")
    kw = kw.replace("?", r"\?")
    kw = kw.replace("{", r"\{")
    kw = kw.replace("}", r"\}")
    kw = kw.replace("~", r"\~")

    return kw
