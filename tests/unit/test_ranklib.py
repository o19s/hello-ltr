"""
Unit tests for ranklib.py module.

Tests cover:
- check_for_rankymcrankface function
- write_training_set function
- train_model function
- save_model function
- train function
- feature_search function
"""

from unittest.mock import Mock, mock_open, patch

import pytest

from ltr.judgments import Judgment
from ltr.ranklib import (
    DEFAULT_RANKLIB_TIMEOUT_SECONDS,
    check_for_rankymcrankface,
    feature_search,
    save_model,
    train,
    train_model,
    write_training_set,
)


class TestCheckForRankyMcRankFace:
    """Test check_for_rankymcrankface function."""

    @patch("ltr.ranklib.download")
    @patch("tempfile.gettempdir")
    @patch("os.path.exists")
    @patch("os.access")
    def test_check_for_rankymcrankface_downloads_jar(
        self, mock_access, mock_exists, mock_tempdir, mock_download
    ):
        """Test check_for_rankymcrankface downloads jar file."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = True  # JAR file exists after download
        mock_access.return_value = True  # JAR file is readable
        # Act
        result = check_for_rankymcrankface()
        # Assert
        assert result == "/tmp/RankyMcRankFace.jar"
        mock_download.assert_called_once()
        call_args = mock_download.call_args
        assert "RankyMcRankFace.jar" in call_args[0][0][0]


class TestWriteTrainingSet:
    """Test write_training_set function."""

    @patch("ltr.judgments.judgments_to_file")
    @patch("tempfile.gettempdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    def test_write_training_set(
        self, mock_exists, mock_file, mock_tempdir, mock_judgments_to_file
    ):
        """Test write_training_set writes training set to file."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = True  # File exists after write
        training_set = [Mock(), Mock()]
        # Act
        result = write_training_set(training_set)  # type: ignore[arg-type]
        # Assert
        assert result == "/tmp/training.txt"
        mock_judgments_to_file.assert_called_once()
        mock_file.assert_called_once_with("/tmp/training.txt", "w")


class TestTrainModel:
    """Test train_model function."""

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    def test_train_model_basic(
        self,
        mock_getsize,
        mock_exists,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test train_model with basic parameters."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"  # Java is available
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_result = Mock()
        mock_result.returncode = 0  # Success
        mock_result.stdout = "Training log output"
        mock_result.stderr = None
        mock_subprocess.return_value = mock_result
        mock_parsed_result = Mock()
        mock_parsed_result.trainingLogs = [Mock()]  # Non-empty logs
        mock_parse.return_value = mock_parsed_result
        mock_exists.return_value = True  # Model file exists
        mock_getsize.return_value = 100  # Model file has content
        # Create minimal valid training set (2 judgments with features)
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0, 3.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[4.0, 5.0, 6.0]
            ),
        ]
        # Act
        result = train_model(training_set, "/tmp/model.txt")
        # Assert
        assert result is not None
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        # subprocess.run receives a list of arguments
        cmd_str = " ".join(call_args)
        assert "java" in cmd_str
        assert "-jar" in cmd_str
        assert "-ranker" in cmd_str
        assert "6" in cmd_str
        assert "-train" in cmd_str
        assert "/tmp/training.txt" in cmd_str
        assert "-save" in cmd_str
        assert "/tmp/model.txt" in cmd_str
        # Verify timeout parameter is passed
        call_kwargs = mock_subprocess.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == DEFAULT_RANKLIB_TIMEOUT_SECONDS

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    @patch("builtins.open", new_callable=mock_open)
    @patch("tempfile.gettempdir")
    @patch("os.path.exists")
    @patch("os.path.getsize")
    def test_train_model_with_features(
        self,
        mock_getsize,
        mock_exists,
        mock_tempdir,
        mock_file,
        mock_which,
        mock_check,
        mock_write,
        mock_subprocess,
        mock_parse,
    ):
        """Test train_model with features parameter."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_which.return_value = "/usr/bin/java"  # Java is available
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_result = Mock()
        mock_result.returncode = 0  # Success
        mock_result.stdout = "Training log output"
        mock_result.stderr = None
        mock_subprocess.return_value = mock_result
        mock_parsed_result = Mock()
        mock_parsed_result.trainingLogs = [Mock()]  # Non-empty logs
        mock_parse.return_value = mock_parsed_result
        mock_exists.return_value = True  # Model file exists
        mock_getsize.return_value = 100  # Model file has content
        # Create minimal valid training set (2 judgments with features)
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0, 3.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[4.0, 5.0, 6.0]
            ),
        ]
        features = [1, 2, 3]
        # Act
        train_model(training_set, "/tmp/model.txt", features=features)
        # Assert
        call_args = mock_subprocess.call_args[0][0]
        # subprocess.run receives a list of arguments
        cmd_str = " ".join(call_args)
        assert "-feature" in cmd_str
        mock_file.assert_called()
        # Verify timeout parameter is passed
        call_kwargs = mock_subprocess.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == DEFAULT_RANKLIB_TIMEOUT_SECONDS

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    def test_train_model_with_kcv(
        self, mock_which, mock_check, mock_write, mock_subprocess, mock_parse
    ):
        """Test train_model with kcv parameter."""
        # Arrange
        mock_which.return_value = "/usr/bin/java"  # Java is available
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_result = Mock()
        mock_result.returncode = 0  # Success
        mock_result.stdout = "Training log output"
        mock_result.stderr = None
        mock_subprocess.return_value = mock_result
        mock_parsed_result = Mock()
        mock_parsed_result.trainingLogs = [Mock()]  # Non-empty logs
        mock_parse.return_value = mock_parsed_result
        # Create minimal valid training set (2 judgments with features)
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0, 3.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[4.0, 5.0, 6.0]
            ),
        ]
        # Act
        train_model(training_set, "/tmp/model.txt", kcv=5)
        # Assert
        call_args = mock_subprocess.call_args[0][0]
        # subprocess.run receives a list of arguments
        cmd_str = " ".join(call_args)
        assert "-kcv" in cmd_str
        assert "5" in cmd_str
        # Verify timeout parameter is passed
        call_kwargs = mock_subprocess.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == DEFAULT_RANKLIB_TIMEOUT_SECONDS

    @patch("ltr.ranklib.parse_training_log")
    @patch("subprocess.run")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("shutil.which")
    def test_train_model_timeout(
        self, mock_which, mock_check, mock_write, mock_subprocess, mock_parse
    ):
        """Test train_model handles timeout correctly."""
        # Arrange
        import subprocess

        mock_which.return_value = "/usr/bin/java"  # Java is available
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="java", timeout=300)
        # Create minimal valid training set (2 judgments with features)
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0, 3.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[4.0, 5.0, 6.0]
            ),
        ]
        # Act & Assert
        from ltr.exceptions import ModelError

        with pytest.raises(ModelError, match="timed out"):
            train_model(training_set, "/tmp/model.txt")


class TestSaveModel:
    """Test save_model function."""

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="model definition")
    def test_save_model(self, mock_file, mock_exists):
        """Test save_model reads file and submits to client."""
        # Arrange
        mock_client = Mock()
        mock_exists.return_value = True  # File exists
        # Act
        save_model(mock_client, "model1", "/tmp/model.txt", "index1", "featureset1")
        # Assert
        mock_exists.assert_called_once_with("/tmp/model.txt")
        mock_file.assert_called_once_with("/tmp/model.txt")
        mock_client.submit_ranklib_model.assert_called_once_with(
            "featureset1", "index1", "model1", "model definition"
        )


class TestTrain:
    """Test train function."""

    @patch("ltr.ranklib.save_model")
    @patch("ltr.ranklib.train_model")
    @patch("ltr.ranklib._validate_training_prerequisites")
    def test_train_success(self, mock_validate, mock_train_model, mock_save_model):
        """Test train function with successful training."""
        # Arrange
        mock_client = Mock()
        # Create minimal valid training set (2 judgments with features)
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0, 3.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[4.0, 5.0, 6.0]
            ),
        ]
        mock_result = Mock()
        mock_result.trainingLogs = [Mock()]  # Non-empty logs
        mock_train_model.return_value = mock_result
        # Act
        result = train(mock_client, training_set, "model1", "featureset1", "index1")
        # Assert
        mock_train_model.assert_called_once()
        mock_save_model.assert_called_once()
        assert result == mock_result

    @patch("ltr.ranklib.train_model")
    @patch("ltr.ranklib._validate_training_prerequisites")
    def test_train_fails_with_no_logs(self, mock_validate, mock_train_model):
        """Test train raises ModelError when no training logs."""
        # Arrange
        mock_client = Mock()
        # Create minimal valid training set (2 judgments with features)
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0, 3.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[4.0, 5.0, 6.0]
            ),
        ]
        mock_result = Mock()
        mock_result.trainingLogs = []  # Empty logs
        mock_train_model.return_value = mock_result
        # Act & Assert
        from ltr.exceptions import ModelError

        with pytest.raises(ModelError, match="Training failed"):
            train(mock_client, training_set, "model1", "featureset1", "index1")

    @patch("ltr.ranklib.save_model")
    @patch("ltr.ranklib.train_model")
    @patch("ltr.ranklib._validate_training_prerequisites")
    def test_train_with_kcv_skips_save(
        self, mock_validate, mock_train_model, mock_save_model
    ):
        """Test train skips save_model when kcv is used."""
        # Arrange
        mock_client = Mock()
        # Create minimal valid training set (2 judgments with features)
        training_set = [
            Judgment(
                grade=3, qid=1, keywords="test", doc_id="doc1", features=[1.0, 2.0, 3.0]
            ),
            Judgment(
                grade=2, qid=1, keywords="test", doc_id="doc2", features=[4.0, 5.0, 6.0]
            ),
        ]
        mock_result = Mock()
        mock_result.trainingLogs = [Mock()]
        mock_train_model.return_value = mock_result
        # Act
        result = train(
            mock_client, training_set, "model1", "featureset1", "index1", kcv=5
        )
        # Assert
        assert result is not None
        mock_save_model.assert_not_called()


class TestFeatureSearch:
    """Test feature_search function."""

    @patch("ltr.ranklib.train_model")
    def test_feature_search_finds_best_combo(self, mock_train_model):
        """Test feature_search finds best feature combination."""
        # Arrange
        mock_client = Mock()
        training_set = []
        features = [1, 2, 3]

        # Mock results for different combinations
        def mock_train_side_effect(*args, **kwargs):
            """Mock side effect that returns different metrics based on feature combination.

            Args:
                *args: Positional arguments (unused)
                **kwargs: Keyword arguments, expects 'features' key

            Returns:
                Mock: Mock result object with kcvTestAvg attribute
            """
            mock_result = Mock()
            # Return different metrics based on features
            # feature_search passes features as a list, not tuple
            features_arg = kwargs.get("features")
            if features_arg == [1]:
                mock_result.kcvTestAvg = 0.5
            elif features_arg == [2]:
                mock_result.kcvTestAvg = 0.6
            elif features_arg == [1, 2]:
                mock_result.kcvTestAvg = 0.7  # Best
            else:
                mock_result.kcvTestAvg = 0.4
            return mock_result

        mock_train_model.side_effect = mock_train_side_effect
        # Act
        best_combo, metric_per_feature = feature_search(
            mock_client, training_set, "featureset", features=features, kcv=5
        )
        # Assert
        assert best_combo is not None
        assert best_combo.kcvTestAvg == 0.7
        assert isinstance(metric_per_feature, dict)

    @patch("ltr.ranklib.train_model")
    def test_feature_search_handles_failed_training(self, mock_train_model):
        """Test feature_search handles failed training gracefully."""
        # Arrange
        mock_client = Mock()
        training_set = []
        features = [1]

        mock_result = Mock()
        mock_result.kcvTestAvg = None  # Failed training
        mock_train_model.return_value = mock_result
        # Act
        best_combo, metric_per_feature = feature_search(
            mock_client, training_set, "featureset", features=features, kcv=5
        )
        # Assert
        # Should not crash, best_combo might be None
        assert best_combo is None or best_combo.kcvTestAvg is None
        # metric_per_feature should still be populated
        assert isinstance(metric_per_feature, dict)
