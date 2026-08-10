"""Tests for ltr.download module.

This module tests file download functionality including error handling.
"""

import importlib
from unittest.mock import Mock, patch

import pytest
import requests

from ltr.download import download, download_one

# ltr/__init__.py does `from .download import download`, which rebinds the
# attribute `ltr.download` to the function and shadows the submodule of the same
# name, so string patch targets naming that submodule cannot be resolved by
# mock.patch. Grab the real module object and patch attributes on it instead.
download_module = importlib.import_module("ltr.download")


class TestDownloadOne:
    """Test the download_one function."""

    def test_download_one_creates_directory(self, tmp_path):
        """Test that download_one creates destination directory if it doesn't exist."""
        dest = tmp_path / "new_dir"
        url = "http://example.com/test.txt"

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"test content"]
            mock_get.return_value = mock_response

            download_one(uri=url, dest=str(dest))
            assert dest.exists()
            assert dest.is_dir()

    def test_download_one_raises_error_if_dest_not_directory(self, tmp_path):
        """Test that download_one raises ValueError if dest exists but is not a directory."""
        file_path = tmp_path / "existing_file.txt"
        file_path.write_text("existing")

        with pytest.raises(ValueError, match="is not a directory"):
            download_one(uri="http://example.com/test.txt", dest=str(file_path))

    def test_download_one_skips_existing_file(self, tmp_path, caplog):
        """Test that download_one skips download if file already exists."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        existing_file = dest_dir / "test.txt"
        existing_file.write_text("existing content")

        url = "http://example.com/test.txt"

        with patch.object(download_module.requests, "get") as mock_get:
            download_one(uri=url, dest=str(dest_dir), force=False)
            # Should not call requests.get if file exists
            mock_get.assert_not_called()

    def test_download_one_force_redownload(self, tmp_path, caplog):
        """Test that download_one re-downloads if force=True."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        existing_file = dest_dir / "test.txt"
        existing_file.write_text("old content")

        url = "http://example.com/test.txt"
        new_content = b"new content"

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [new_content]
            mock_get.return_value = mock_response

            download_one(uri=url, dest=str(dest_dir), force=True)
            mock_get.assert_called_once()

            # File should be overwritten
            assert existing_file.read_bytes() == new_content

    def test_download_one_downloads_file(self, tmp_path):
        """Test that download_one downloads and saves file correctly."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/test.txt"
        file_content = b"test file content"

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [file_content]
            mock_get.return_value = mock_response

            download_one(uri=url, dest=str(dest_dir))

            # Verify file was downloaded
            downloaded_file = dest_dir / "test.txt"
            assert downloaded_file.exists()
            assert downloaded_file.read_bytes() == file_content

    def test_download_one_handles_chunked_download(self, tmp_path):
        """Test that download_one handles chunked downloads correctly."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/large.txt"
        chunks = [b"chunk1", b"chunk2", b"chunk3"]

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = chunks
            mock_get.return_value = mock_response

            download_one(uri=url, dest=str(dest_dir))

            # Verify all chunks were written
            downloaded_file = dest_dir / "large.txt"
            assert downloaded_file.read_bytes() == b"chunk1chunk2chunk3"

    def test_download_one_handles_empty_chunks(self, tmp_path):
        """Test that download_one skips empty chunks."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/test.txt"
        chunks = [b"content", b"", b"more"]

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = chunks
            mock_get.return_value = mock_response

            download_one(uri=url, dest=str(dest_dir))

            # Empty chunks should be skipped
            downloaded_file = dest_dir / "test.txt"
            assert downloaded_file.read_bytes() == b"contentmore"

    def test_download_one_extracts_filename_from_url(self, tmp_path):
        """Test that download_one extracts filename from URL."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/path/to/file.json"

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"content"]
            mock_get.return_value = mock_response

            download_one(uri=url, dest=str(dest_dir))

            # Should use filename from URL
            downloaded_file = dest_dir / "file.json"
            assert downloaded_file.exists()

    def test_download_one_handles_requests_error(self, tmp_path):
        """Test that download_one propagates requests errors."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/test.txt"

        with patch.object(download_module.requests, "get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError(
                "Connection failed"
            )

            with pytest.raises(requests.exceptions.ConnectionError):
                download_one(uri=url, dest=str(dest_dir))


class TestDownload:
    """Test the download function."""

    def test_download_multiple_files(self, tmp_path):
        """Test that download downloads multiple files."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        urls = [
            "http://example.com/file1.txt",
            "http://example.com/file2.txt",
            "http://example.com/file3.txt",
        ]

        with patch.object(download_module, "download_one") as mock_download_one:
            download(uris=urls, dest=str(dest_dir))

            # Should call download_one for each URL
            assert mock_download_one.call_count == 3
            for url in urls:
                mock_download_one.assert_any_call(
                    uri=url, dest=str(dest_dir), force=False
                )

    def test_download_passes_force_parameter(self, tmp_path):
        """Test that download passes force parameter to download_one."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        urls = ["http://example.com/file1.txt"]

        with patch.object(download_module, "download_one") as mock_download_one:
            download(uris=urls, dest=str(dest_dir), force=True)
            mock_download_one.assert_called_once_with(
                uri=urls[0], dest=str(dest_dir), force=True
            )

    def test_download_handles_iterable(self, tmp_path):
        """Test that download handles iterable (not just list)."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        urls = ("http://example.com/file1.txt", "http://example.com/file2.txt")

        with patch.object(download_module, "download_one") as mock_download_one:
            download(uris=urls, dest=str(dest_dir))
            assert mock_download_one.call_count == 2

    def test_download_empty_list(self, tmp_path):
        """Test that download handles empty list."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch.object(download_module, "download_one") as mock_download_one:
            download(uris=[], dest=str(dest_dir))
            mock_download_one.assert_not_called()

    def test_download_propagates_errors(self, tmp_path):
        """Test that download propagates errors from download_one."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        urls = ["http://example.com/file1.txt", "http://example.com/file2.txt"]

        with patch.object(download_module, "download_one") as mock_download_one:
            mock_download_one.side_effect = [
                None,  # First download succeeds
                ValueError("Download failed"),  # Second download fails
            ]

            with pytest.raises(ValueError, match="Download failed"):
                download(uris=urls, dest=str(dest_dir))

    def test_download_creates_directory(self, tmp_path):
        """Test that download creates destination directory."""
        dest_dir = tmp_path / "new_download_dir"
        urls = ["http://example.com/file.txt"]

        with patch.object(download_module, "download_one") as mock_download_one:
            download(uris=urls, dest=str(dest_dir))
            # download_one should be called, which will create the directory
            mock_download_one.assert_called_once()


class TestDownloadErrorHandling:
    """Test error handling in download functions."""

    def test_download_one_handles_network_timeout(self, tmp_path):
        """Test that download_one handles network timeout."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/test.txt"

        with patch.object(download_module.requests, "get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

            with pytest.raises(requests.exceptions.Timeout):
                download_one(uri=url, dest=str(dest_dir))

    def test_download_one_handles_http_error(self, tmp_path):
        """An error status must propagate, not be written out as the file."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/test.txt"

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "404 Not Found", response=mock_response
            )
            mock_response.iter_content.return_value = [b"<html>Not Found</html>"]
            mock_get.return_value = mock_response

            with pytest.raises(requests.exceptions.HTTPError):
                download_one(uri=url, dest=str(dest_dir))

        assert not (dest_dir / "test.txt").exists(), (
            "An error page must not be cached as the requested file"
        )

    def test_download_one_handles_file_write_error(self, tmp_path):
        """Test that download_one handles file write errors."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        url = "http://example.com/test.txt"

        with (
            patch.object(download_module.requests, "get") as mock_get,
            patch.object(
                download_module.os, "fdopen", side_effect=OSError("Permission denied")
            ),
        ):
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"content"]
            mock_get.return_value = mock_response

            with pytest.raises(OSError, match="Permission denied"):
                download_one(uri=url, dest=str(dest_dir))


class TestDownloadCachePoisoning:
    """Tests that a failed download cannot become a permanent cache entry.

    Regression coverage for issue #119. Downloads used to be written straight
    to the destination path, so an interrupted transfer left a zero-byte file
    that the existence check then treated as valid. One bad network moment
    became a permanent failure, and it surfaced far downstream - an empty
    judgment file yields no features, so the notebook fails several cells later
    with something like "'LinearSVC' object has no attribute 'coef_'", naming
    nothing to do with the download.
    """

    def test_failed_download_leaves_no_file(self, tmp_path):
        """A connection failure must not create the destination file."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch.object(download_module.requests, "get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure")

            with pytest.raises(requests.exceptions.ConnectionError):
                download_one(uri="http://example.com/data.txt", dest=str(dest_dir))

        assert not (dest_dir / "data.txt").exists()

    def test_failed_download_leaves_no_partial_file(self, tmp_path):
        """The temporary file must be cleaned up too, not just the target."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.side_effect = (
                requests.exceptions.ChunkedEncodingError("connection broken mid-stream")
            )
            mock_get.return_value = mock_response

            with pytest.raises(requests.exceptions.ChunkedEncodingError):
                download_one(uri="http://example.com/data.txt", dest=str(dest_dir))

        assert list(dest_dir.iterdir()) == [], (
            "A failed transfer must leave the destination directory untouched"
        )

    def test_empty_cached_file_is_redownloaded(self, tmp_path):
        """Repair caches already poisoned by the old behaviour."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        poisoned = dest_dir / "data.txt"
        poisoned.write_bytes(b"")

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"real content"]
            mock_get.return_value = mock_response

            download_one(uri="http://example.com/data.txt", dest=str(dest_dir))

            mock_get.assert_called_once()

        assert poisoned.read_bytes() == b"real content"

    def test_nonempty_cached_file_is_still_skipped(self, tmp_path):
        """The caching behaviour itself must survive: a good file is reused."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        cached = dest_dir / "data.txt"
        cached.write_bytes(b"already here")

        with patch.object(download_module.requests, "get") as mock_get:
            download_one(uri="http://example.com/data.txt", dest=str(dest_dir))

            mock_get.assert_not_called()

        assert cached.read_bytes() == b"already here"

    def test_failed_forced_redownload_preserves_existing_file(self, tmp_path):
        """force=True used to truncate the good file before fetching."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        cached = dest_dir / "data.txt"
        cached.write_bytes(b"good existing content")

        with patch.object(download_module.requests, "get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure")

            with pytest.raises(requests.exceptions.ConnectionError):
                download_one(
                    uri="http://example.com/data.txt", dest=str(dest_dir), force=True
                )

        assert cached.read_bytes() == b"good existing content", (
            "A failed re-download must not destroy the copy already on disk"
        )

    def test_successful_download_writes_expected_bytes(self, tmp_path):
        """The atomic rename must still deliver the whole file."""
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with patch.object(download_module.requests, "get") as mock_get:
            mock_response = Mock()
            mock_response.iter_content.return_value = [b"chunk1", b"chunk2", b"chunk3"]
            mock_get.return_value = mock_response

            download_one(uri="http://example.com/data.txt", dest=str(dest_dir))

        assert (dest_dir / "data.txt").read_bytes() == b"chunk1chunk2chunk3"
        assert list(dest_dir.iterdir()) == [dest_dir / "data.txt"], (
            "No temporary files may be left behind on success"
        )
