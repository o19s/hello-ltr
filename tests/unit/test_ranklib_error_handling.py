"""
Unit tests for error handling in ranklib.py module.

Tests cover error handling improvements:
- Java availability check
- Download failure handling
- File I/O error handling
- Subprocess exception handling
- Model file verification
"""

from unittest.mock import Mock, mock_open, patch

import pytest
import requests

from ltr.exceptions import ModelError
from ltr.judgments import Judgment
from ltr.ranklib import (
    check_for_rankymcrankface,
    train_model,
    write_training_set,
)


class TestCheckForRankyMcRankFaceErrorHandling:
    """Test error handling in check_for_rankymcrankface function."""

    @patch("ltr.ranklib.download")
    @patch("tempfile.gettempdir")
    @patch("os.path.exists")
    @patch("os.access")
    def test_download_failure_raises_model_error(
        self, mock_access, mock_exists, mock_tempdir, mock_download
    ):
        """Test that download failures raise ModelError with helpful message."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = False
        mock_download.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        # Act & Assert
        with pytest.raises(ModelError, match="Failed to download"):
            check_for_rankymcrankface()

    @patch("ltr.ranklib.download")
    @patch("tempfile.gettempdir")
    @patch("os.path.exists")
    def test_jar_not_found_after_download_raises_error(
        self, mock_exists, mock_tempdir, mock_download
    ):
        """Test that missing JAR file after download raises ModelError."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = False  # JAR file doesn't exist after download
        mock_download.return_value = None  # Download "succeeds" but file missing

        # Act & Assert
        with pytest.raises(ModelError, match="was not found at expected location"):
            check_for_rankymcrankface()

    @patch("ltr.ranklib.download")
    @patch("tempfile.gettempdir")
    @patch("os.path.exists")
    @patch("os.access")
    def test_jar_not_readable_raises_error(
        self, mock_access, mock_exists, mock_tempdir, mock_download
    ):
        """Test that unreadable JAR file raises ModelError."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = True  # File exists
        mock_access.return_value = False  # But not readable
        mock_download.return_value = None

        # Act & Assert
        with pytest.raises(ModelError, match="is not readable"):
            check_for_rankymcrankface()


class TestWriteTrainingSetErrorHandling:
    """Test error handling in write_training_set function."""

    @patch("ltr.judgments.judgments_to_file")
    @patch("tempfile.gettempdir")
    @patch("builtins.open")
    @patch("os.path.exists")
    def test_file_write_failure_raises_model_error(
        self, mock_exists, mock_open_func, mock_tempdir, mock_judgments_to_file
    ):
        """Test that file write failures raise ModelError."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_open_func.side_effect = OSError("Permission denied")
        mock_exists.return_value = False
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            )
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="Failed to write training set"):
            write_training_set(training_set)

    @patch("ltr.judgments.judgments_to_file")
    @patch("tempfile.gettempdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    def test_file_not_created_raises_error(
        self, mock_exists, mock_file, mock_tempdir, mock_judgments_to_file
    ):
        """Test that missing file after write raises ModelError."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = False  # File doesn't exist after write
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            )
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="was not created"):
            write_training_set(training_set)


class TestTrainModelErrorHandling:
    """Test error handling in train_model function."""

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    def test_java_not_found_raises_model_error(
        self,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test that missing Java raises ModelError."""
        # Arrange
        mock_which.return_value = None  # Java not found
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[3.0, 4.0]
            ),
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="Java is not installed"):
            train_model(training_set, "/tmp/model.txt")

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    @patch("builtins.open", new_callable=mock_open)
    @patch("tempfile.gettempdir")
    @patch("os.path.exists")
    def test_feature_file_write_failure_raises_error(
        self,
        mock_exists,
        mock_tempdir,
        mock_file,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test that feature file write failures raise ModelError."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_tempdir.return_value = "/tmp"
        mock_file.side_effect = OSError("Disk full")
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Training log output"
        mock_subprocess.return_value = mock_result
        mock_parsed_result = Mock()
        mock_parsed_result.trainingLogs = [Mock()]
        mock_parse.return_value = mock_parsed_result
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[3.0, 4.0]
            ),
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="Failed to write features file"):
            train_model(training_set, "/tmp/model.txt", features=[1, 2])

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    def test_subprocess_filenotfound_raises_error(
        self,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test that FileNotFoundError from subprocess raises ModelError."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_subprocess.side_effect = FileNotFoundError("java: command not found")
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[3.0, 4.0]
            ),
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="Java executable not found"):
            train_model(training_set, "/tmp/model.txt")

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    def test_subprocess_oserror_raises_error(
        self,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test that OSError from subprocess raises ModelError."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_subprocess.side_effect = OSError("Too many open files")
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[3.0, 4.0]
            ),
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="OS error while running RankLib"):
            train_model(training_set, "/tmp/model.txt")

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    def test_model_file_not_created_raises_error(
        self,
        mock_getsize,
        mock_exists,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test that missing model file after training raises ModelError."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_result = Mock()
        mock_result.returncode = 0  # Success
        mock_result.stdout = "Training log output"
        mock_result.stderr = None
        mock_subprocess.return_value = mock_result
        mock_parsed_result = Mock()
        mock_parsed_result.trainingLogs = [Mock()]  # Has logs
        mock_parse.return_value = mock_parsed_result
        mock_exists.return_value = False  # Model file doesn't exist
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[3.0, 4.0]
            ),
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="model file was not created"):
            train_model(training_set, "/tmp/model.txt")

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    def test_model_file_empty_raises_error(
        self,
        mock_getsize,
        mock_exists,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test that empty model file raises ModelError."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_result = Mock()
        mock_result.returncode = 0  # Success
        mock_result.stdout = "Training log output"
        mock_result.stderr = None
        mock_subprocess.return_value = mock_result
        mock_parsed_result = Mock()
        mock_parsed_result.trainingLogs = [Mock()]  # Has logs
        mock_parse.return_value = mock_parsed_result
        mock_exists.return_value = True  # File exists
        mock_getsize.return_value = 0  # But is empty
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[3.0, 4.0]
            ),
        ]

        # Act & Assert
        with pytest.raises(ModelError, match="is empty"):
            train_model(training_set, "/tmp/model.txt")

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    @patch("os.path.exists")
    def test_model_file_verification_skipped_for_kcv(
        self,
        mock_exists,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test that model file verification is skipped when using KCV."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_result = Mock()
        mock_result.returncode = 0  # Success
        mock_result.stdout = "Training log output"
        mock_result.stderr = None
        mock_subprocess.return_value = mock_result
        mock_parsed_result = Mock()
        mock_parsed_result.trainingLogs = [Mock()]  # Has logs
        mock_parse.return_value = mock_parsed_result
        # Model file doesn't exist, but that's OK for KCV
        mock_exists.return_value = False
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[3.0, 4.0]
            ),
        ]

        # Act - Should not raise error because KCV doesn't save models
        result = train_model(training_set, "/tmp/model.txt", kcv=5)

        # Assert
        assert result is not None
        # Verify that exists was not called (verification skipped for KCV)
        # Actually, exists might be called, but the check for file existence
        # should be skipped when kcv is set
        assert mock_parse.called
