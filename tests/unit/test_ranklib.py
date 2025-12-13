"""
Unit tests for ranklib.py module.

Tests cover:
- check_for_rankymcrankface function
- write_training_set function
- trainModel function
- save_model function
- train function
- feature_search function
"""

from unittest.mock import Mock, mock_open, patch

import pytest

from ltr.ranklib import (
    check_for_rankymcrankface,
    feature_search,
    save_model,
    train,
    trainModel,
    write_training_set,
)


class TestCheckForRankyMcRankFace:
    """Test check_for_rankymcrankface function."""

    @patch("ltr.ranklib.download")
    @patch("tempfile.gettempdir")
    def test_check_for_rankymcrankface_downloads_jar(self, mock_tempdir, mock_download):
        """Test check_for_rankymcrankface downloads jar file."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
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
    def test_write_training_set(self, mock_file, mock_tempdir, mock_judgments_to_file):
        """Test write_training_set writes training set to file."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        training_set = [Mock(), Mock()]
        # Act
        result = write_training_set(training_set)
        # Assert
        assert result == "/tmp/training.txt"
        mock_judgments_to_file.assert_called_once()
        mock_file.assert_called_once_with("/tmp/training.txt", "w")


class TestTrainModel:
    """Test trainModel function."""

    @patch("ltr.ranklib.parse_training_log")
    @patch("os.popen")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    def test_train_model_basic(self, mock_check, mock_write, mock_popen, mock_parse):
        """Test trainModel with basic parameters."""
        # Arrange
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_popen.return_value.read.return_value = "Training log output"
        mock_parse.return_value = Mock()
        training_set = []
        # Act
        result = trainModel(training_set, "/tmp/model.txt")
        # Assert
        assert result is not None
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert "java -jar" in call_args
        assert "-ranker 6" in call_args
        assert "-train /tmp/training.txt" in call_args
        assert "-save /tmp/model.txt" in call_args

    @patch("ltr.ranklib.parse_training_log")
    @patch("os.popen")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    @patch("builtins.open", new_callable=mock_open)
    @patch("tempfile.gettempdir")
    def test_train_model_with_features(
        self, mock_tempdir, mock_file, mock_check, mock_write, mock_popen, mock_parse
    ):
        """Test trainModel with features parameter."""
        # Arrange
        mock_tempdir.return_value = "/tmp"
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_popen.return_value.read.return_value = "Training log output"
        mock_parse.return_value = Mock()
        training_set = []
        features = [1, 2, 3]
        # Act
        trainModel(training_set, "/tmp/model.txt", features=features)
        # Assert
        call_args = mock_popen.call_args[0][0]
        assert "-feature" in call_args
        mock_file.assert_called()

    @patch("ltr.ranklib.parse_training_log")
    @patch("os.popen")
    @patch("ltr.ranklib.write_training_set")
    @patch("ltr.ranklib.check_for_rankymcrankface")
    def test_train_model_with_kcv(self, mock_check, mock_write, mock_popen, mock_parse):
        """Test trainModel with kcv parameter."""
        # Arrange
        mock_check.return_value = "/tmp/ranky.jar"
        mock_write.return_value = "/tmp/training.txt"
        mock_popen.return_value.read.return_value = "Training log output"
        mock_parse.return_value = Mock()
        training_set = []
        # Act
        trainModel(training_set, "/tmp/model.txt", kcv=5)
        # Assert
        call_args = mock_popen.call_args[0][0]
        assert "-kcv 5" in call_args


class TestSaveModel:
    """Test save_model function."""

    @patch("builtins.open", new_callable=mock_open, read_data="model definition")
    def test_save_model(self, mock_file):
        """Test save_model reads file and submits to client."""
        # Arrange
        mock_client = Mock()
        # Act
        save_model(mock_client, "model1", "/tmp/model.txt", "index1", "featureset1")
        # Assert
        mock_file.assert_called_once_with("/tmp/model.txt")
        mock_client.submit_ranklib_model.assert_called_once_with(
            "featureset1", "index1", "model1", "model definition"
        )


class TestTrain:
    """Test train function."""

    @patch("ltr.ranklib.save_model")
    @patch("ltr.ranklib.trainModel")
    def test_train_success(self, mock_train_model, mock_save_model):
        """Test train function with successful training."""
        # Arrange
        mock_client = Mock()
        training_set = []
        mock_result = Mock()
        mock_result.trainingLogs = [Mock()]  # Non-empty logs
        mock_train_model.return_value = mock_result
        # Act
        result = train(mock_client, training_set, "model1", "featureset1", "index1")
        # Assert
        mock_train_model.assert_called_once()
        mock_save_model.assert_called_once()
        assert result == mock_result

    @patch("ltr.ranklib.trainModel")
    def test_train_fails_with_no_logs(self, mock_train_model):
        """Test train raises RuntimeError when no training logs."""
        # Arrange
        mock_client = Mock()
        training_set = []
        mock_result = Mock()
        mock_result.trainingLogs = []  # Empty logs
        mock_train_model.return_value = mock_result
        # Act & Assert
        with pytest.raises(RuntimeError, match="Training failed"):
            train(mock_client, training_set, "model1", "featureset1", "index1")

    @patch("ltr.ranklib.save_model")
    @patch("ltr.ranklib.trainModel")
    def test_train_with_kcv_skips_save(self, mock_train_model, mock_save_model):
        """Test train skips save_model when kcv is used."""
        # Arrange
        mock_client = Mock()
        training_set = []
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

    @patch("ltr.ranklib.trainModel")
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
            if kwargs.get("features") == (1,):
                mock_result.kcvTestAvg = 0.5
            elif kwargs.get("features") == (2,):
                mock_result.kcvTestAvg = 0.6
            elif kwargs.get("features") == (1, 2):
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

    @patch("ltr.ranklib.trainModel")
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
