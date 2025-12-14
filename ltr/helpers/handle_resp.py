"""HTTP response handling and error reporting utilities.

This module provides functions for handling HTTP responses from search engines,
printing status messages, and optionally raising errors for non-2xx status codes.
"""


def resp_msg(msg, resp, throw=True, ignore=None):
    """Print response message and optionally raise error for non-2xx status codes.

    Args:
        msg: Message to print
        resp: Response object with status_code and text attributes
        throw: Whether to raise exception on error status codes (default: True)
        ignore: List of status codes to ignore when checking for errors (default: None)

    Raises:
        RuntimeError: If status code >= 400, not in ignore list, and throw=True
    """
    if ignore is None:
        ignore = []
    rsc = resp.status_code
    print(f"{msg} [Status: {rsc}]")
    if rsc >= 400 and rsc not in ignore and throw:
        raise RuntimeError(resp.text)
