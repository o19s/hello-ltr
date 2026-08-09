"""Unit tests for convert helper module."""

from ltr.helpers.convert import convert, parse_splits
from ltr.types import FeatureList


class TestParseSplits:
    """Test parse_splits function."""

    def test_parse_leaf_node(self):
        """Test parsing a leaf node with feature and output."""
        # Arrange
        import xml.etree.ElementTree as ET

        xml_str = """
        <split>
            <feature>1</feature>
            <output>0.5</output>
        </split>
        """
        split = ET.fromstring(xml_str)
        features: FeatureList = [{"name": "feature1"}]

        # Act
        result = parse_splits(split, features)

        # Assert
        assert result["feature"] == "feature1"
        assert result["value"] == "0.5"

    def test_parse_split_node_with_threshold(self):
        """Test parsing a split node with threshold."""
        # Arrange
        import xml.etree.ElementTree as ET

        xml_str = """
        <split>
            <feature>1</feature>
            <threshold>0.5</threshold>
        </split>
        """
        split = ET.fromstring(xml_str)
        features: FeatureList = [{"name": "feature1"}]

        # Act
        result = parse_splits(split, features)

        # Assert
        assert result["feature"] == "feature1"
        assert result["threshold"] == "0.5"

    def test_parse_split_node_with_children(self):
        """Test parsing a split node with left and right children."""
        # Arrange
        import xml.etree.ElementTree as ET

        xml_str = """
        <split>
            <feature>1</feature>
            <threshold>0.5</threshold>
            <split pos="left">
                <feature>2</feature>
                <output>0.3</output>
            </split>
            <split pos="right">
                <feature>2</feature>
                <output>0.7</output>
            </split>
        </split>
        """
        split = ET.fromstring(xml_str)
        features: FeatureList = [
            {"name": "feature1"},
            {"name": "feature2"},
        ]

        # Act
        result = parse_splits(split, features)

        # Assert
        assert result["feature"] == "feature1"
        assert result["threshold"] == "0.5"
        assert "left" in result
        assert "right" in result
        assert result["left"]["feature"] == "feature2"
        assert result["left"]["value"] == "0.3"
        assert result["right"]["feature"] == "feature2"
        assert result["right"]["value"] == "0.7"

    def test_parse_nested_splits(self):
        """Test parsing deeply nested split nodes."""
        # Arrange
        import xml.etree.ElementTree as ET

        xml_str = """
        <split>
            <feature>1</feature>
            <threshold>0.5</threshold>
            <split pos="left">
                <feature>2</feature>
                <threshold>0.3</threshold>
                <split pos="left">
                    <feature>3</feature>
                    <output>0.1</output>
                </split>
                <split pos="right">
                    <feature>3</feature>
                    <output>0.2</output>
                </split>
            </split>
            <split pos="right">
                <feature>2</feature>
                <output>0.7</output>
            </split>
        </split>
        """
        split = ET.fromstring(xml_str)
        features: FeatureList = [
            {"name": "feature1"},
            {"name": "feature2"},
            {"name": "feature3"},
        ]

        # Act
        result = parse_splits(split, features)

        # Assert
        assert result["feature"] == "feature1"
        assert result["threshold"] == "0.5"
        assert result["left"]["feature"] == "feature2"
        assert result["left"]["threshold"] == "0.3"
        assert result["left"]["left"]["value"] == "0.1"
        assert result["left"]["right"]["value"] == "0.2"
        assert result["right"]["value"] == "0.7"

    def test_feature_index_conversion(self):
        """Test that feature indices are correctly converted (1-based to 0-based)."""
        # Arrange
        import xml.etree.ElementTree as ET

        xml_str = """
        <split>
            <feature>3</feature>
            <output>0.5</output>
        </split>
        """
        split = ET.fromstring(xml_str)
        features: FeatureList = [
            {"name": "feature1"},
            {"name": "feature2"},
            {"name": "feature3"},
        ]

        # Act
        result = parse_splits(split, features)

        # Assert
        # Feature index 3 (1-based) should map to features[2] (0-based)
        assert result["feature"] == "feature3"

    def test_whitespace_handling(self):
        """Test that whitespace in XML text is stripped."""
        # Arrange
        import xml.etree.ElementTree as ET

        xml_str = """
        <split>
            <feature>  1  </feature>
            <threshold>  0.5  </threshold>
            <output>  0.3  </output>
        </split>
        """
        split = ET.fromstring(xml_str)
        features: FeatureList = [{"name": "feature1"}]

        # Act
        result = parse_splits(split, features)

        # Assert
        assert result["feature"] == "feature1"
        assert result["threshold"] == "0.5"
        assert result["value"] == "0.3"


class TestConvert:
    """Test convert function."""

    def test_convert_basic_model(self):
        """Test converting a basic LambdaMART model."""
        # Arrange
        ensemble_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<ensemble>
    <tree id="1" weight="1.0">
        <split>
            <feature>1</feature>
            <threshold>0.5</threshold>
            <split pos="left">
                <feature>2</feature>
                <output>0.3</output>
            </split>
            <split pos="right">
                <feature>2</feature>
                <output>0.7</output>
            </split>
        </split>
    </tree>
</ensemble>"""
        # Add header lines that will be stripped
        header_lines = "\n".join(["# Header line"] * 7)
        ensemble_xml_string = header_lines + "\n" + ensemble_xml

        model_name = "test_model"
        feature_set = "test_features"
        feature_mapping: FeatureList = [
            {"name": "feature1"},
            {"name": "feature2"},
        ]

        # Act
        result = convert(ensemble_xml_string, model_name, feature_set, feature_mapping)

        # Assert
        assert result["store"] == feature_set
        assert result["name"] == model_name
        assert result["class"] == "org.apache.solr.ltr.model.MultipleAdditiveTreesModel"
        assert result["features"] == feature_mapping
        assert "params" in result
        assert "trees" in result["params"]
        assert len(result["params"]["trees"]) == 1
        assert result["params"]["trees"][0]["weight"] == "1.0"
        assert "root" in result["params"]["trees"][0]

    def test_convert_multiple_trees(self):
        """Test converting a model with multiple trees."""
        # Arrange
        ensemble_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<ensemble>
    <tree id="1" weight="0.5">
        <split>
            <feature>1</feature>
            <output>0.3</output>
        </split>
    </tree>
    <tree id="2" weight="0.5">
        <split>
            <feature>2</feature>
            <output>0.7</output>
        </split>
    </tree>
</ensemble>"""
        header_lines = "\n".join(["# Header line"] * 7)
        ensemble_xml_string = header_lines + "\n" + ensemble_xml

        model_name = "test_model"
        feature_set = "test_features"
        feature_mapping: FeatureList = [
            {"name": "feature1"},
            {"name": "feature2"},
        ]

        # Act
        result = convert(ensemble_xml_string, model_name, feature_set, feature_mapping)

        # Assert
        assert len(result["params"]["trees"]) == 2
        assert result["params"]["trees"][0]["weight"] == "0.5"
        assert result["params"]["trees"][1]["weight"] == "0.5"

    def test_convert_strips_header(self):
        """Test that convert strips the first 7 lines (header)."""
        # Arrange
        header_lines = "\n".join([f"# Header line {i}" for i in range(7)])
        ensemble_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<ensemble>
    <tree id="1" weight="1.0">
        <split>
            <feature>1</feature>
            <output>0.5</output>
        </split>
    </tree>
</ensemble>"""
        ensemble_xml_string = header_lines + "\n" + ensemble_xml

        model_name = "test_model"
        feature_set = "test_features"
        feature_mapping: FeatureList = [{"name": "feature1"}]

        # Act
        result = convert(ensemble_xml_string, model_name, feature_set, feature_mapping)

        # Assert - Should successfully parse despite header lines
        assert result["name"] == model_name
        assert len(result["params"]["trees"]) == 1

    def test_convert_tree_structure(self):
        """Test that tree structure is correctly converted."""
        # Arrange
        ensemble_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<ensemble>
    <tree id="1" weight="1.0">
        <split>
            <feature>1</feature>
            <threshold>0.5</threshold>
            <split pos="left">
                <feature>2</feature>
                <output>0.3</output>
            </split>
            <split pos="right">
                <feature>2</feature>
                <output>0.7</output>
            </split>
        </split>
    </tree>
</ensemble>"""
        header_lines = "\n".join(["# Header"] * 7)
        ensemble_xml_string = header_lines + "\n" + ensemble_xml

        model_name = "test_model"
        feature_set = "test_features"
        feature_mapping: FeatureList = [
            {"name": "feature1"},
            {"name": "feature2"},
        ]

        # Act
        result = convert(ensemble_xml_string, model_name, feature_set, feature_mapping)

        # Assert
        root = result["params"]["trees"][0]["root"]
        assert root["feature"] == "feature1"
        assert root["threshold"] == "0.5"
        assert root["left"]["feature"] == "feature2"
        assert root["left"]["value"] == "0.3"
        assert root["right"]["feature"] == "feature2"
        assert root["right"]["value"] == "0.7"

    def test_convert_weight_as_string(self):
        """Test that tree weights are converted to strings."""
        # Arrange
        ensemble_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<ensemble>
    <tree id="1" weight="0.75">
        <split>
            <feature>1</feature>
            <output>0.5</output>
        </split>
    </tree>
</ensemble>"""
        header_lines = "\n".join(["# Header"] * 7)
        ensemble_xml_string = header_lines + "\n" + ensemble_xml

        model_name = "test_model"
        feature_set = "test_features"
        feature_mapping: FeatureList = [{"name": "feature1"}]

        # Act
        result = convert(ensemble_xml_string, model_name, feature_set, feature_mapping)

        # Assert
        assert result["params"]["trees"][0]["weight"] == "0.75"
        assert isinstance(result["params"]["trees"][0]["weight"], str)
