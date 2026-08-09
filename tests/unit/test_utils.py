"""
Test helper utilities for improved error reporting and debugging.

This module provides utilities to enhance test error messages with context,
making it easier to debug test failures.
"""


def assert_equal_with_context(actual, expected, context_msg=None):
    """
    Assert that two values are equal, with optional context message.

    Args:
        actual: The actual value
        expected: The expected value
        context_msg: Optional message providing context about what was being tested
    Raises:
        AssertionError: If values are not equal, with detailed error message
    """
    if actual != expected:
        error_msg = "\nAssertion failed: Values are not equal"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nExpected: {expected!r}"
        error_msg += f"\nActual: {actual!r}"
        error_msg += f"\nType(expected): {type(expected).__name__}"
        error_msg += f"\nType(actual): {type(actual).__name__}"
        raise AssertionError(error_msg)
    return True


def assert_in_with_context(item, container, context_msg=None):
    """
    Assert that an item is in a container, with optional context message.

    Args:
        item: The item to check for
        container: The container to search in
        context_msg: Optional message providing context about what was being tested

    Raises:
        AssertionError: If item is not in container, with detailed error message
    """
    if item not in container:
        error_msg = "\nAssertion failed: Item not found in container"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nItem: {item!r}"
        error_msg += f"\nContainer: {container!r}"
        if hasattr(container, "__len__"):
            error_msg += f"\nContainer length: {len(container)}"
        raise AssertionError(error_msg)
    return True


def assert_not_in_with_context(item, container, context_msg=None):
    """
    Assert that an item is not in a container, with optional context message.

    Args:
        item: The item to check for
        container: The container to search in
        context_msg: Optional message providing context about what was being tested

    Raises:
        AssertionError: If item is in container, with detailed error message
    """
    if item in container:
        error_msg = "\nAssertion failed: Item unexpectedly found in container"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nItem: {item!r}"
        error_msg += f"\nContainer: {container!r}"
        raise AssertionError(error_msg)
    return True


def assert_is_instance_with_context(obj, expected_type, context_msg=None):
    """
    Assert that an object is an instance of the expected type, with context.

    Args:
        obj: The object to check
        expected_type: The expected type (can be a tuple of types)
        context_msg: Optional message providing context about what was being tested

    Raises:
        AssertionError: If object is not an instance of expected type
    """
    if not isinstance(obj, expected_type):
        error_msg = "\nAssertion failed: Object is not an instance of expected type"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nObject: {obj!r}"
        error_msg += f"\nObject type: {type(obj).__name__}"
        if isinstance(expected_type, tuple):
            expected_names = [t.__name__ for t in expected_type]
            error_msg += f"\nExpected types: {', '.join(expected_names)}"
        else:
            error_msg += f"\nExpected type: {expected_type.__name__}"
        raise AssertionError(error_msg)
    return True


def assert_has_attr_with_context(obj, attr_name, context_msg=None):
    """
    Assert that an object has a specific attribute, with context.

    Args:
        obj: The object to check
        attr_name: The name of the attribute to check for
        context_msg: Optional message providing context about what was being tested

    Raises:
        AssertionError: If object does not have the attribute
    """
    if not hasattr(obj, attr_name):
        error_msg = "\nAssertion failed: Object does not have expected attribute"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nObject: {obj!r}"
        error_msg += f"\nObject type: {type(obj).__name__}"
        error_msg += f"\nExpected attribute: {attr_name}"
        if hasattr(obj, "__dict__"):
            available_attrs = [k for k in dir(obj) if not k.startswith("_")]
            if available_attrs:
                error_msg += (
                    f"\nAvailable attributes: {', '.join(available_attrs[:10])}"
                )
        raise AssertionError(error_msg)
    return True


def format_call_args(call_args, call_kwargs):
    """
    Format function call arguments for error messages.

    Args:
        call_args: Tuple of positional arguments
        call_kwargs: Dict of keyword arguments

    Returns:
        Formatted string describing the call
    """
    parts = []
    if call_args:
        parts.append(f"args={call_args!r}")
    if call_kwargs:
        parts.append(f"kwargs={call_kwargs!r}")
    return ", ".join(parts) if parts else "no arguments"


def assert_called_with_context(
    mock_obj, expected_args=None, expected_kwargs=None, context_msg=None, call_index=0
):
    """
    Assert that a mock was called with specific arguments, with context.

    Args:
        mock_obj: The mock object to check
        expected_args: Expected positional arguments (None to skip check)
        expected_kwargs: Expected keyword arguments (None to skip check)
        context_msg: Optional message providing context
        call_index: Which call to check (default: 0 for first call)

    Raises:
        AssertionError: If mock was not called with expected arguments
    """
    if not mock_obj.called:
        error_msg = "\nAssertion failed: Mock was not called"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nMock: {mock_obj}"
        raise AssertionError(error_msg)

    if call_index >= len(mock_obj.call_args_list):
        error_msg = "\nAssertion failed: Mock was not called enough times"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nExpected call index: {call_index}"
        error_msg += f"\nActual number of calls: {len(mock_obj.call_args_list)}"
        raise AssertionError(error_msg)

    actual_call = mock_obj.call_args_list[call_index]
    actual_args, actual_kwargs = actual_call

    errors = []
    if expected_args is not None and actual_args != expected_args:
        errors.append(
            f"Positional args mismatch: expected {expected_args!r}, got {actual_args!r}"
        )
    if expected_kwargs is not None:
        # Check that all expected kwargs are present and match
        for key, expected_value in expected_kwargs.items():
            if key not in actual_kwargs:
                errors.append(f"Missing keyword argument: {key}")
            elif actual_kwargs[key] != expected_value:
                errors.append(
                    f"Keyword arg '{key}' mismatch: expected {expected_value!r}, got {actual_kwargs[key]!r}"
                )

    if errors:
        error_msg = "\nAssertion failed: Mock call arguments do not match"
        if context_msg:
            error_msg += f"\nContext: {context_msg}"
        error_msg += f"\nCall index: {call_index}"
        error_msg += f"\nActual call: {format_call_args(actual_args, actual_kwargs)}"
        if expected_args is not None:
            error_msg += f"\nExpected args: {expected_args!r}"
        if expected_kwargs is not None:
            error_msg += f"\nExpected kwargs: {expected_kwargs!r}"
        error_msg += "\n" + "\n".join(f"  - {e}" for e in errors)
        raise AssertionError(error_msg)

    return True


def create_bulk_side_effect_for_missing_id():
    """
    Create a bulk side effect function that triggers ValueError for missing ID tests.

    This helper is used in tests that verify error handling when documents
    are indexed without an 'id' field. The side effect consumes the actions
    generator to trigger the ValueError that occurs during iteration.

    Returns:
        function: A side effect function that can be used with mock_bulk.side_effect

    Example:
        ```python
        mock_bulk.side_effect = create_bulk_side_effect_for_missing_id()
        ```
    """

    def bulk_side_effect(client, actions, **kwargs):
        """Side effect function that triggers ValueError by consuming actions generator.

        Args:
            client: Search client (unused)
            actions: Generator of actions to index
            **kwargs: Additional arguments (unused)

        Returns:
            tuple: (0, []) - success count and errors list
        """
        # Try to iterate to trigger the ValueError
        list(actions)  # Consume generator to trigger ValueError
        return (0, [])

    return bulk_side_effect


def create_safe_resp_msg_wrapper():
    """
    Create a safe resp_msg wrapper for BulkResp objects.

    BulkResp objects from elasticsearch/opensearch helpers don't have a 'text'
    attribute like regular response objects. This wrapper safely handles both
    types of response objects.

    Returns:
        function: A wrapper function that can be used with mock_resp_msg.side_effect

    Example:
        ```python
        mock_resp_msg.side_effect = create_safe_resp_msg_wrapper()
        ```
    """

    def safe_resp_msg(msg, resp, throw=True, ignore=None):
        """Safe wrapper for resp_msg that handles BulkResp objects without text attribute.

        Args:
            msg: Message to print
            resp: Response object (BulkResp or similar)
            throw: Whether to raise exception on error status
            ignore: List of status codes to ignore
        """
        if ignore is None:
            ignore = []
        rsc = resp.status_code
        print(f"{msg} [Status: {rsc}]")
        if rsc >= 400 and rsc not in ignore and throw:
            text = getattr(resp, "text", "")
            raise RuntimeError(text)

    return safe_resp_msg
