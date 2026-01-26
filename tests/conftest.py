"""
Pytest configuration and shared fixtures for EchoMind tests.
"""

import os
import sys

import pytest

# Add src directory to Python path for imports
src_path = os.path.join(os.path.dirname(__file__), "..", "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)


@pytest.fixture
def mock_database_url() -> str:
    """Provide a mock database URL for testing."""
    return "postgresql://testuser:testpass@localhost:5432/testdb"


@pytest.fixture
def mock_asyncpg_url() -> str:
    """Provide a mock asyncpg database URL for testing."""
    return "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"
