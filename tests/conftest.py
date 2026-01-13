"""
Pytest configuration and shared fixtures.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock

from app.services.musicbrainz_service import MusicBrainzService


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for tests."""
    temp_dir = tempfile.mkdtemp()
    cache_dir = Path(temp_dir) / "cache"
    yield cache_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def musicbrainz_service(temp_cache_dir):
    """Create a MusicBrainzService instance with temporary cache."""
    return MusicBrainzService(cache_dir=temp_cache_dir)


@pytest.fixture
def mock_musicbrainz_service():
    """Create a mocked MusicBrainzService."""
    return Mock(spec=MusicBrainzService)

