"""Unit tests for defaultlist helper module."""

import pytest

from ltr.helpers.defaultlist import DefaultList, defaultlist


class TestDefaultList:
    """Test DefaultList class functionality."""

    def test_initialization(self):
        """Test DefaultList initialization with factory function."""
        # Arrange & Act
        dl = DefaultList(lambda: 0)

        # Assert
        assert len(dl) == 0
        assert dl.factory is not None

    def test_getitem_with_default(self):
        """Test that accessing missing indices creates default values."""
        # Arrange
        dl = DefaultList(lambda: 0)

        # Act
        value = dl[5]

        # Assert
        assert value == 0
        assert len(dl) == 6  # Indices 0-5 created
        assert dl[0] == 0
        assert dl[1] == 0
        assert dl[5] == 0

    def test_getitem_existing(self):
        """Test accessing existing indices."""
        # Arrange
        dl = DefaultList(lambda: 0)
        dl.append(1)
        dl.append(2)

        # Act & Assert
        assert dl[0] == 1
        assert dl[1] == 2

    def test_setitem_with_expansion(self):
        """Test setting values at indices beyond current length."""
        # Arrange
        dl = DefaultList(lambda: 0)

        # Act
        dl[5] = 42

        # Assert
        assert len(dl) == 6
        assert dl[0] == 0  # Default value
        assert dl[5] == 42  # Set value

    def test_setitem_existing(self):
        """Test setting values at existing indices."""
        # Arrange
        dl = DefaultList(lambda: 0)
        dl.append(1)

        # Act
        dl[0] = 99

        # Assert
        assert dl[0] == 99
        assert len(dl) == 1

    def test_slice_getitem(self):
        """Test that slice indexing works correctly."""
        # Arrange
        dl = DefaultList(lambda: 0)
        dl[5] = 42

        # Act
        slice_result = dl[0:3]

        # Assert
        assert isinstance(slice_result, list)
        assert slice_result == [0, 0, 0]

    def test_slice_setitem(self):
        """Test setting values using slice notation."""
        # Arrange
        dl = DefaultList(lambda: 0)
        dl[5] = 42  # Expand to length 6

        # Act
        dl[0:3] = [1, 2, 3]

        # Assert
        assert dl[0] == 1
        assert dl[1] == 2
        assert dl[2] == 3
        assert dl[5] == 42  # Unchanged

    def test_slice_setitem_invalid_type(self):
        """Test that slice setitem raises TypeError for non-list values."""
        # Arrange
        dl = DefaultList(lambda: 0)

        # Act & Assert
        with pytest.raises(TypeError, match="must be a list"):
            dl[0:3] = "not a list"  # type: ignore[arg-type]

    def test_custom_factory(self):
        """Test DefaultList with custom factory function."""
        # Arrange
        counter = [0]  # Use list to allow modification in closure

        def factory():
            counter[0] += 1
            return counter[0]

        dl = DefaultList(factory)

        # Act
        val1 = dl[0]
        val2 = dl[1]
        val3 = dl[0]  # Should return existing value, not create new

        # Assert
        assert val1 == 1
        assert val2 == 2
        assert val3 == 1  # Existing value, factory not called again
        assert len(dl) == 2


class TestDefaultlistFunction:
    """Test defaultlist factory function."""

    def test_defaultlist_function(self):
        """Test that defaultlist() creates DefaultList instances."""
        # Arrange & Act
        dl = defaultlist(lambda: "default")

        # Assert
        assert isinstance(dl, DefaultList)
        assert dl.factory is not None
        assert dl[0] == "default"
