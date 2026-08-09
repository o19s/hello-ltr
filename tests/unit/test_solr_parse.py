"""
Unit tests for Solr parsing utilities.

Tests cover:
- every_other_zipped function
- dictify function
- parse_named_list function
- parse_termvect_namedlist function
"""

from ltr.client.solr_parse import (
    dictify,
    every_other_zipped,
    parse_named_list,
    parse_termvect_namedlist,
)


class TestEveryOtherZipped:
    """Test every_other_zipped function."""

    def test_every_other_zipped_basic(self):
        """Test zipping every other element into pairs."""
        # Arrange
        lst = [0, 1, 2, 3, 4, 5]

        # Act
        result = list(every_other_zipped(lst))

        # Assert
        assert result == [(0, 1), (2, 3), (4, 5)]

    def test_every_other_zipped_empty(self):
        """Test with empty list."""
        # Arrange
        lst = []

        # Act
        result = list(every_other_zipped(lst))

        # Assert
        assert result == []

    def test_every_other_zipped_two_elements(self):
        """Test with two elements."""
        # Arrange
        lst = ["key", "value"]

        # Act
        result = list(every_other_zipped(lst))

        # Assert
        assert result == [("key", "value")]

    def test_every_other_zipped_strings(self):
        """Test with string elements."""
        # Arrange
        lst = ["a", "b", "c", "d"]

        # Act
        result = list(every_other_zipped(lst))

        # Assert
        assert result == [("a", "b"), ("c", "d")]


class TestDictify:
    """Test dictify function."""

    def test_dictify_unique_keys(self):
        """Test dictify with unique keys returns dict."""
        # Arrange
        nl_tups = [("key1", "value1"), ("key2", "value2"), ("key3", "value3")]

        # Act
        result = dictify(nl_tups)

        # Assert
        assert isinstance(result, dict)
        assert result == {"key1": "value1", "key2": "value2", "key3": "value3"}

    def test_dictify_duplicate_keys(self):
        """Test dictify with duplicate keys returns list."""
        # Arrange
        nl_tups = [("key1", "value1"), ("key1", "value2"), ("key2", "value3")]

        # Act
        result = dictify(nl_tups)

        # Assert
        assert isinstance(result, list)
        assert result == nl_tups

    def test_dictify_empty(self):
        """Test dictify with empty list."""
        # Arrange
        nl_tups = []

        # Act
        result = dictify(nl_tups)

        # Assert
        assert isinstance(result, dict)
        assert result == {}

    def test_dictify_single_pair(self):
        """Test dictify with single key-value pair."""
        # Arrange
        nl_tups = [("key", "value")]

        # Act
        result = dictify(nl_tups)

        # Assert
        assert isinstance(result, dict)
        assert result == {"key": "value"}


class TestParseNamedList:
    """Test parse_named_list function."""

    def test_parse_named_list_simple(self):
        """Test parsing simple named list."""
        # Arrange
        lst = ["key1", "value1", "key2", "value2"]

        # Act
        result = parse_named_list(lst)

        # Assert
        assert isinstance(result, dict)
        assert result == {"key1": "value1", "key2": "value2"}

    def test_parse_named_list_nested(self):
        """Test parsing nested named list."""
        # Arrange
        lst = [
            "outer_key",
            ["inner_key1", "inner_value1", "inner_key2", "inner_value2"],
            "outer_key2",
            "outer_value2",
        ]

        # Act
        result = parse_named_list(lst)

        # Assert
        assert isinstance(result, dict)
        assert result["outer_key"] == {
            "inner_key1": "inner_value1",
            "inner_key2": "inner_value2",
        }
        assert result["outer_key2"] == "outer_value2"

    def test_parse_named_list_deeply_nested(self):
        """Test parsing deeply nested named list."""
        # Arrange
        lst = [
            "level1",
            [
                "level2",
                [
                    "level3",
                    ["level4_key", "level4_value"],
                ],
            ],
        ]

        # Act
        result = parse_named_list(lst)

        # Assert
        assert isinstance(result, dict)
        assert result["level1"]["level2"]["level3"] == {"level4_key": "level4_value"}

    def test_parse_named_list_duplicate_keys(self):
        """Test parsing named list with duplicate keys returns list."""
        # Arrange
        lst = ["key", "value1", "key", "value2"]

        # Act
        result = parse_named_list(lst)

        # Assert
        assert isinstance(result, list)
        assert result == [("key", "value1"), ("key", "value2")]

    def test_parse_named_list_empty(self):
        """Test parsing empty list."""
        # Arrange
        lst = []

        # Act
        result = parse_named_list(lst)

        # Assert
        assert isinstance(result, dict)
        assert result == {}

    def test_parse_named_list_mixed_types(self):
        """Test parsing named list with mixed value types."""
        # Arrange
        lst = ["string_key", "string_value", "int_key", 42, "list_key", [1, 2, 3]]

        # Act
        result = parse_named_list(lst)

        # Assert
        assert isinstance(result, dict)
        assert result["string_key"] == "string_value"
        assert result["int_key"] == 42
        # list_key with [1, 2, 3] will be parsed recursively
        # If keys are not unique, it returns list of tuples
        assert "list_key" in result or isinstance(result.get("list_key"), (list, dict))


class TestParseTermvectNamedlist:
    """Test parse_termvect_namedlist function."""

    def test_parse_termvect_namedlist_basic(self):
        """Test parsing basic term vector named list."""
        # Arrange
        lst = [
            "D100000",
            [
                "uniqueKey",
                "D100000",
                "body",
                [
                    "term1",
                    ["positions", ["position", 92, "position", 113]],
                    "term2",
                    ["positions", ["position", 22]],
                ],
            ],
        ]
        field = "body"

        # Act
        result = parse_termvect_namedlist(lst, field)

        # Assert
        assert isinstance(result, dict)
        assert "D100000" in result
        doc_data = result["D100000"]
        assert "body" in doc_data
        term_vects = doc_data["body"]
        assert "term1" in term_vects
        assert term_vects["term1"]["positions"] == [92, 113]
        assert term_vects["term2"]["positions"] == [22]

    def test_parse_termvect_namedlist_dict_positions(self):
        """Test parsing term vector with dict position format."""
        # Arrange
        lst = [
            "D1",
            [
                "uniqueKey",
                "D1",
                "title",
                [
                    "word",
                    ["positions", {"position": 5}],
                ],
            ],
        ]
        field = "title"

        # Act
        result = parse_termvect_namedlist(lst, field)

        # Assert
        assert isinstance(result, dict)
        doc_data = result["D1"]
        term_vects = doc_data["title"]
        assert term_vects["word"]["positions"] == [5]

    def test_parse_termvect_namedlist_multiple_docs(self):
        """Test parsing term vector with multiple documents."""
        # Arrange
        lst = [
            "D1",
            [
                "uniqueKey",
                "D1",
                "body",
                ["term1", ["positions", ["position", 1]]],
            ],
            "D2",
            [
                "uniqueKey",
                "D2",
                "body",
                ["term2", ["positions", ["position", 2]]],
            ],
        ]
        field = "body"

        # Act
        result = parse_termvect_namedlist(lst, field)

        # Assert
        assert isinstance(result, dict)
        assert "D1" in result
        assert "D2" in result
        assert result["D1"]["body"]["term1"]["positions"] == [1]
        assert result["D2"]["body"]["term2"]["positions"] == [2]

    def test_parse_termvect_namedlist_wrong_field(self):
        """Test parsing term vector with field that doesn't match."""
        # Arrange
        lst = [
            "D1",
            [
                "uniqueKey",
                "D1",
                "body",
                ["term1", ["positions", ["position", 1]]],
            ],
        ]
        field = "title"  # Different field

        # Act
        result = parse_termvect_namedlist(lst, field)

        # Assert
        # Should still parse but not normalize positions for non-matching field
        assert isinstance(result, dict)
        assert "D1" in result

    def test_parse_termvect_namedlist_no_positions(self):
        """Test parsing term vector without positions attribute."""
        # Arrange
        lst = [
            "D1",
            [
                "uniqueKey",
                "D1",
                "body",
                [
                    "term1",
                    ["tf", 5],  # No positions attribute
                ],
            ],
        ]
        field = "body"

        # Act
        result = parse_termvect_namedlist(lst, field)

        # Assert
        assert isinstance(result, dict)
        doc_data = result["D1"]
        term_vects = doc_data["body"]
        assert "term1" in term_vects
        assert "tf" in term_vects["term1"]

    def test_parse_termvect_namedlist_complex_example(self):
        """Test parsing complex term vector example from module docstring."""
        # Arrange
        solr_nl = [
            "D100000",
            [
                "uniqueKey",
                "D100000",
                "body",
                [
                    "1",
                    ["positions", ["position", 92, "position", 113]],
                    "2",
                    ["positions", ["position", 22, "position", 413]],
                    "boo",
                    [
                        "positions",
                        [
                            "position",
                            22,
                        ],
                    ],
                ],
            ],
        ]
        field = "body"

        # Act
        result = parse_termvect_namedlist(solr_nl, field)

        # Assert
        assert isinstance(result, dict)
        doc_data = result["D100000"]
        term_vects = doc_data["body"]
        assert term_vects["1"]["positions"] == [92, 113]
        assert term_vects["2"]["positions"] == [22, 413]
        assert term_vects["boo"]["positions"] == [22]

    def test_parse_termvect_namedlist_non_dict_result(self):
        """Test parsing term vector that returns list (duplicate keys)."""
        # Arrange
        lst = ["key", "value1", "key", "value2"]  # Duplicate keys
        field = "body"

        # Act
        result = parse_termvect_namedlist(lst, field)

        # Assert
        # Should return list when keys are not unique
        assert isinstance(result, list)
