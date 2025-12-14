"""Default list implementation with automatic expansion.

This module provides a list-like data structure that automatically creates
default values for missing indices, similar to defaultdict but for lists.
"""


class DefaultList(list):
    """List that automatically creates default values for missing indices.

    When accessing or setting an index beyond the current list length, the list
    is automatically extended with default values created by the factory function.

    Adapted from: https://stackoverflow.com/a/869901/8123

    Attributes:
        factory: Callable that creates default values when extending the list.
    """

    def __init__(self, factory):
        """Initialize a DefaultList with a factory function.

        Args:
            factory: Callable that takes no arguments and returns a default value.
        """
        self.factory = factory

    def __getitem__(self, index):
        """Get item at index, extending list with defaults if necessary.

        Args:
            index: Index to retrieve.

        Returns:
            Value at index, or default value if index was beyond list length.
        """
        size = len(self)
        if index >= size:
            self.extend(self.factory() for _ in range(size, index + 1))

        return list.__getitem__(self, index)

    def __setitem__(self, index, value):
        """Set item at index, extending list with defaults if necessary.

        Args:
            index: Index to set.
            value: Value to set at index.
        """
        size = len(self)
        if index >= size:
            self.extend(self.factory() for _ in range(size, index + 1))

        list.__setitem__(self, index, value)


def defaultlist(factory):
    """Create a DefaultList with the given factory function.

    Args:
        factory: Callable that takes no arguments and returns a default value.

    Returns:
        DefaultList: New DefaultList instance.
    """
    return DefaultList(factory)
