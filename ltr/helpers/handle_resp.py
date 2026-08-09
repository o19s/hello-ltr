"""HTTP response handling and error reporting utilities.

This module provides functions for handling HTTP responses from search engines,
logging status messages, and optionally raising errors for non-2xx status codes.
"""

from __future__ import annotations

from typing import Any

from ltr.exceptions import ClientError
from ltr.logger import get_logger

logger = get_logger(__name__)


def resp_msg(
    msg: str,
    resp: Any,
    throw: bool = True,
    ignore: list[int] | None = None,
) -> None:
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
    if rsc >= 400:
        logger.error(f"{msg} [Status: {rsc}]")
    else:
        logger.info(f"{msg} [Status: {rsc}]")
    if rsc >= 400 and rsc not in ignore and throw:
        raise ClientError(
            f"HTTP {rsc} error: {resp.text}",
            operation=msg,
        )
