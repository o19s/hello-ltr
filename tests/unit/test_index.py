"""
Unit tests for index.py module.

Tests cover:
- rebuild function with various scenarios
- Index existence checking
- Force rebuild behavior
"""

from unittest.mock import Mock

from ltr.index import rebuild


class TestRebuild:
    """Test rebuild function."""

    def test_rebuild_index_exists_no_force(self):
        """Test rebuild when index exists and force=False prints message."""
        # Arrange
        mock_client = Mock()
        mock_client.check_index_exists.return_value = True
        # Act
        result = rebuild(mock_client, "test_index", [], force=False)
        # Assert
        assert result is None
        mock_client.create_index.assert_not_called()
        mock_client.delete_index.assert_not_called()

    def test_rebuild_index_exists_with_force(self):
        """Test rebuild when index exists and force=True deletes and recreates."""
        # Arrange
        mock_client = Mock()
        mock_client.check_index_exists.return_value = True
        doc_src = [{"id": "1", "title": "Test"}]
        # Act
        rebuild(mock_client, "test_index", doc_src, force=True)
        # Assert
        assert mock_client.delete_index.called, (
            f"Expected delete_index to be called when force=True and index exists. Calls: {mock_client.delete_index.call_args_list}"
        )
        mock_client.delete_index.assert_called_once_with("test_index")
        assert mock_client.create_index.called, (
            f"Expected create_index to be called after delete. Calls: {mock_client.create_index.call_args_list}"
        )
        mock_client.create_index.assert_called_once_with("test_index")
        assert mock_client.index_documents.called, (
            f"Expected index_documents to be called with doc_src. Calls: {mock_client.index_documents.call_args_list}"
        )
        mock_client.index_documents.assert_called_once_with(
            "test_index", doc_src=doc_src
        )

    def test_rebuild_index_not_exists(self):
        """Test rebuild when index doesn't exist creates and indexes."""
        # Arrange
        mock_client = Mock()
        mock_client.check_index_exists.return_value = False
        doc_src = [{"id": "1", "title": "Test"}]
        # Act
        rebuild(mock_client, "test_index", doc_src)
        # Assert
        mock_client.delete_index.assert_not_called()
        mock_client.create_index.assert_called_once_with("test_index")
        mock_client.index_documents.assert_called_once_with(
            "test_index", doc_src=doc_src
        )

    def test_rebuild_calls_in_order(self):
        """Test rebuild calls methods in correct order."""
        # Arrange
        mock_client = Mock()
        mock_client.check_index_exists.return_value = False
        doc_src = []
        call_order = []

        def track_call(name):
            """Create a wrapper function that tracks when a method is called.

            Args:
                name: Name to append to call_order when function is called

            Returns:
                function: Wrapper function that tracks calls and returns Mock
            """

            def wrapper(*args, **kwargs):
                """Wrapper function that tracks call order.

                Args:
                    *args: Positional arguments (unused)
                    **kwargs: Keyword arguments (unused)

                Returns:
                    Mock: Mock object
                """
                call_order.append(name)
                return Mock()

            return wrapper

        mock_client.create_index.side_effect = track_call("create")
        mock_client.index_documents.side_effect = track_call("index")
        # Act
        rebuild(mock_client, "test_index", doc_src)
        # Assert
        assert call_order == ["create", "index"]
