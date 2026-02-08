"""Tests for checkpoint generator."""

import os
import tempfile
import pytest

from projector.logic.checkpoint_generator import CheckpointGenerator
from projector.logic.exceptions import CheckpointGenerationError


def test_generate_visualization_success():
    """Test successful checkpoint generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = CheckpointGenerator(log_base_dir=tmpdir)

        points = [
            {
                "vector": [0.1, 0.2, 0.3],
                "payload": {"title": "Doc 1", "text": "Sample text content"},
            },
            {
                "vector": [0.4, 0.5, 0.6],
                "payload": {"title": "Doc 2", "text": "Another document"},
            },
            {
                "vector": [0.7, 0.8, 0.9],
                "payload": {"title": "Doc 3", "text": "Third document"},
            },
        ]

        result = generator.generate_visualization(points, "test_collection")

        assert result["num_points"] == 3
        assert result["vector_dim"] == 3
        assert result["viz_id"].startswith("viz-")
        assert os.path.exists(result["log_dir"])
        assert os.path.exists(os.path.join(result["log_dir"], "metadata.tsv"))
        assert os.path.exists(os.path.join(result["log_dir"], "checkpoint"))
        assert os.path.exists(os.path.join(result["log_dir"], "projector_config.pbtxt"))

        # Check metadata.tsv content
        with open(os.path.join(result["log_dir"], "metadata.tsv"), "r") as f:
            lines = f.readlines()
            assert len(lines) == 3
            assert "Doc 1" in lines[0]
            assert "Sample text" in lines[0]


def test_generate_visualization_empty_points():
    """Test error on empty points list."""
    generator = CheckpointGenerator()

    with pytest.raises(CheckpointGenerationError, match="no points provided"):
        generator.generate_visualization([], "test_collection")


def test_generate_visualization_inconsistent_dimensions():
    """Test error on inconsistent vector dimensions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = CheckpointGenerator(log_base_dir=tmpdir)

        points = [
            {"vector": [0.1, 0.2, 0.3], "payload": {"title": "Doc 1"}},
            {"vector": [0.4, 0.5], "payload": {"title": "Doc 2"}},  # Different dimension
        ]

        with pytest.raises(CheckpointGenerationError, match="same dimensionality"):
            generator.generate_visualization(points, "test_collection")


def test_generate_visualization_missing_payload():
    """Test handling of missing payload fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = CheckpointGenerator(log_base_dir=tmpdir)

        points = [
            {"vector": [0.1, 0.2], "payload": {}},  # Empty payload
            {"vector": [0.3, 0.4], "payload": {"title": "Doc 2"}},  # Missing text
            {"vector": [0.5, 0.6], "payload": {"text": "Some text"}},  # Missing title
        ]

        result = generator.generate_visualization(points, "test_collection")

        assert result["num_points"] == 3

        # Check metadata defaults
        with open(os.path.join(result["log_dir"], "metadata.tsv"), "r") as f:
            lines = f.readlines()
            assert "Untitled" in lines[0]  # Default title
            assert "Doc 2" in lines[1]
            assert "Untitled" in lines[2]


def test_generate_visualization_long_text_truncation():
    """Test that long text is truncated to 100 characters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = CheckpointGenerator(log_base_dir=tmpdir)

        long_text = "A" * 200  # 200 characters
        points = [
            {"vector": [0.1, 0.2], "payload": {"title": "Doc", "text": long_text}},
        ]

        result = generator.generate_visualization(points, "test_collection")

        with open(os.path.join(result["log_dir"], "metadata.tsv"), "r") as f:
            line = f.readline()
            # Should contain title + " | " + 100 chars of text
            assert len(line) < 200  # Much less than original 200
            assert line.count("A") == 100  # Exactly 100 'A' characters


def test_generate_visualization_special_characters():
    """Test handling of special characters (newlines, tabs)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = CheckpointGenerator(log_base_dir=tmpdir)

        points = [
            {
                "vector": [0.1],
                "payload": {"title": "Doc\nWith\nNewlines", "text": "Text\twith\ttabs"},
            },
        ]

        result = generator.generate_visualization(points, "test_collection")

        with open(os.path.join(result["log_dir"], "metadata.tsv"), "r") as f:
            line = f.readline().strip()  # Strip the trailing newline
            # Newlines and tabs should be replaced with spaces
            assert "\n" not in line
            assert "\t" not in line  # All tabs should be replaced
            assert "Doc With Newlines" in line
            assert "Text with tabs" in line
