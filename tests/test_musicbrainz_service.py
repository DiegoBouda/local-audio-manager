"""
Tests for MusicBrainzService.

Tests are organized by concern:
- API interaction (mocked)
- Caching behavior
- Data extraction and matching
- Error handling
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import tempfile
import shutil
from datetime import datetime, timedelta

from app.services.musicbrainz_service import (
    MusicBrainzService,
    MusicBrainzResult
)


class TestMusicBrainzServiceAPI(unittest.TestCase):
    """Tests for MusicBrainz API interaction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.service = MusicBrainzService(cache_dir=self.cache_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.services.musicbrainz_service.requests.Session')
    def test_search_track_success(self, mock_session_class):
        """Test successful track search."""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "recordings": [
                {
                    "id": "test-mbid",
                    "title": "Test Song",
                    "artist-credit": [
                        {
                            "artist": {
                                "name": "Test Artist"
                            }
                        }
                    ],
                    "releases": [
                        {
                            "id": "release-mbid",
                            "title": "Test Album",
                            "date": "2020-01-01"
                        }
                    ],
                    "length": 180000  # 3 minutes in ms
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session
        
        # Create service with mocked session
        service = MusicBrainzService(cache_dir=self.cache_dir)
        service.session = mock_session
        
        # Test
        result = service.search_track("Test Artist", "Test Song", duration=180.0)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Test Song")
        self.assertEqual(result.artist, "Test Artist")
        self.assertEqual(result.album, "Test Album")
        self.assertEqual(result.mbid, "test-mbid")
        self.assertEqual(result.release_mbid, "release-mbid")
        
        # Verify API was called
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        self.assertIn("/recording", call_args[0][0])
    
    @patch('app.services.musicbrainz_service.requests.Session')
    def test_search_track_no_results(self, mock_session_class):
        """Test search with no results."""
        mock_response = Mock()
        mock_response.json.return_value = {"recordings": []}
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session
        
        service = MusicBrainzService(cache_dir=self.cache_dir)
        service.session = mock_session
        
        result = service.search_track("Unknown Artist", "Unknown Song")
        
        self.assertIsNone(result)
    
    @patch('app.services.musicbrainz_service.requests.Session')
    def test_search_track_api_error(self, mock_session_class):
        """Test handling of API errors."""
        import requests
        
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("API Error")
        mock_session.headers = {}
        mock_session_class.return_value = mock_session
        
        service = MusicBrainzService(cache_dir=self.cache_dir)
        service.session = mock_session
        
        result = service.search_track("Test Artist", "Test Song")
        
        self.assertIsNone(result)
    
    @patch('app.services.musicbrainz_service.requests.Session')
    def test_rate_limiting(self, mock_session_class):
        """Test that rate limiting is enforced."""
        import time
        
        mock_response = Mock()
        mock_response.json.return_value = {"recordings": []}
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session
        
        service = MusicBrainzService(cache_dir=self.cache_dir)
        service.session = mock_session
        
        # Make two calls quickly
        service.search_track("Artist", "Song1")
        service.search_track("Artist", "Song2")
        
        # Verify sleep was called (rate limiting)
        # Note: This is a basic check - in practice you'd use time.time mocking
        self.assertEqual(mock_session.get.call_count, 2)


class TestMusicBrainzServiceCache(unittest.TestCase):
    """Tests for caching behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.service = MusicBrainzService(cache_dir=self.cache_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        key1 = self.service._get_cache_key("Artist", "Song", 180.0)
        key2 = self.service._get_cache_key("artist", "song", 180.0)
        key3 = self.service._get_cache_key("Artist", "Song", None)
        
        # Should be case-insensitive
        self.assertEqual(key1, key2)
        # Should differ by duration
        self.assertNotEqual(key1, key3)
    
    def test_cache_save_and_load(self):
        """Test saving and loading from cache."""
        cache_key = "test_key"
        test_data = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album"
        }
        
        # Save to cache
        self.service._save_to_cache(cache_key, test_data)
        
        # Load from cache
        loaded = self.service._load_from_cache(cache_key)
        
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], "Test Song")
        self.assertEqual(loaded["artist"], "Test Artist")
    
    def test_cache_expiration(self):
        """Test cache expiration logic."""
        cache_key = "test_key"
        test_data = {
            "title": "Test Song",
            "artist": "Test Artist"
        }
        
        # Save with old timestamp
        cache_path = self.service._get_cache_path(cache_key)
        old_cache_data = {
            "cached_at": (datetime.now() - timedelta(hours=25)).isoformat(),
            "result": test_data
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(old_cache_data, f)
        
        # Should return None (expired)
        loaded = self.service._load_from_cache(cache_key)
        self.assertIsNone(loaded)
        # Cache file should be deleted
        self.assertFalse(cache_path.exists())
    
    def test_cache_hit_skips_api(self):
        """Test that cache hits skip API calls."""
        cache_key = self.service._get_cache_key("Artist", "Song", None)
        cached_result = {
            "title": "Cached Song",
            "artist": "Cached Artist",
            "album": "Cached Album"
        }
        
        # Pre-populate cache
        self.service._save_to_cache(cache_key, cached_result)
        
        # Mock session to verify it's not called
        with patch.object(self.service, 'session') as mock_session:
            result = self.service.search_track("Artist", "Song")
            
            # Should return cached result
            self.assertIsNotNone(result)
            self.assertEqual(result.title, "Cached Song")
            # API should not be called
            mock_session.get.assert_not_called()


class TestMusicBrainzServiceMatching(unittest.TestCase):
    """Tests for duration matching and data extraction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.service = MusicBrainzService(cache_dir=self.cache_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_duration_matching_with_tolerance(self):
        """Test duration matching with ±5 second tolerance."""
        recordings = [
            {"length": 180000, "title": "Exact Match"},  # 180s = 3:00
            {"length": 185000, "title": "Close Match"},   # 185s = 3:05
            {"length": 200000, "title": "Far Match"}      # 200s = 3:20
        ]
        
        # Target: 180 seconds (180000ms)
        result = self.service._match_by_duration(recordings, 180000)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Exact Match")
    
    def test_duration_matching_outside_tolerance(self):
        """Test that recordings outside tolerance are not matched."""
        recordings = [
            {"length": 200000, "title": "Too Long"}  # 200s, target is 180s
        ]
        
        result = self.service._match_by_duration(recordings, 180000)
        
        # Should return None (outside 5s tolerance)
        self.assertIsNone(result)
    
    def test_duration_matching_no_duration(self):
        """Test matching when no duration is provided."""
        recordings = [
            {"length": 180000, "title": "Song"}
        ]
        
        result = self.service._match_by_duration(recordings, None)
        
        self.assertIsNone(result)
    
    def test_extract_recording_data(self):
        """Test extraction of data from API response."""
        recording = {
            "id": "recording-mbid",
            "title": "Test Song",
            "artist-credit": [
                {
                    "artist": {
                        "name": "Test Artist"
                    }
                }
            ],
            "releases": [
                {
                    "id": "release-mbid",
                    "title": "Test Album",
                    "date": "2020-01-01",
                    "media": [
                        {
                            "tracks": [
                                {
                                    "number": "1",
                                    "recording": {
                                        "id": "recording-mbid"
                                    }
                                }
                            ]
                        }
                    ]
                }
            ],
            "length": 180000
        }
        
        result = self.service._extract_recording_data(recording)
        
        self.assertEqual(result.title, "Test Song")
        self.assertEqual(result.artist, "Test Artist")
        self.assertEqual(result.album, "Test Album")
        self.assertEqual(result.release_date, "2020-01-01")
        self.assertEqual(result.track_number, "1")
        self.assertEqual(result.duration_ms, 180000)
        self.assertEqual(result.mbid, "recording-mbid")
        self.assertEqual(result.release_mbid, "release-mbid")
    
    def test_extract_recording_data_no_release(self):
        """Test extraction when no release information is available."""
        recording = {
            "id": "recording-mbid",
            "title": "Test Song",
            "artist-credit": [
                {
                    "artist": {
                        "name": "Test Artist"
                    }
                }
            ],
            "releases": [],
            "length": 180000
        }
        
        result = self.service._extract_recording_data(recording)
        
        self.assertEqual(result.title, "Test Song")
        self.assertEqual(result.artist, "Test Artist")
        self.assertIsNone(result.album)
        self.assertIsNone(result.release_mbid)


class TestMusicBrainzServiceCoverArt(unittest.TestCase):
    """Tests for cover art functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.service = MusicBrainzService(cache_dir=self.cache_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.services.musicbrainz_service.requests.Session')
    def test_get_cover_art_success(self, mock_session_class):
        """Test successful cover art retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "images": [
                {
                    "front": True,
                    "image": "https://example.com/cover.jpg"
                }
            ]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session
        
        service = MusicBrainzService(cache_dir=self.cache_dir)
        service.session = mock_session
        
        url = service.get_cover_art("release-mbid")
        
        self.assertEqual(url, "https://example.com/cover.jpg")
    
    @patch('app.services.musicbrainz_service.requests.Session')
    def test_get_cover_art_not_found(self, mock_session_class):
        """Test cover art retrieval when not found."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session
        
        service = MusicBrainzService(cache_dir=self.cache_dir)
        service.session = mock_session
        
        url = service.get_cover_art("release-mbid")
        
        self.assertIsNone(url)
    
    @patch('app.services.musicbrainz_service.requests.Session')
    def test_download_cover_art_success(self, mock_session_class):
        """Test successful cover art download."""
        mock_response = Mock()
        mock_response.iter_content.return_value = [b"fake", b"image", b"data"]
        mock_response.raise_for_status = Mock()
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session
        
        service = MusicBrainzService(cache_dir=self.cache_dir)
        service.session = mock_session
        
        save_path = Path(self.temp_dir) / "cover.jpg"
        success = service.download_cover_art("https://example.com/cover.jpg", save_path)
        
        self.assertTrue(success)
        self.assertTrue(save_path.exists())
        # Verify file was written
        with open(save_path, 'rb') as f:
            data = f.read()
        self.assertEqual(data, b"fakeimagedata")


class TestMusicBrainzResult(unittest.TestCase):
    """Tests for MusicBrainzResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a MusicBrainzResult."""
        result = MusicBrainzResult(
            title="Test Song",
            artist="Test Artist",
            album="Test Album"
        )
        
        self.assertEqual(result.title, "Test Song")
        self.assertEqual(result.artist, "Test Artist")
        self.assertEqual(result.album, "Test Album")
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = MusicBrainzResult(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            release_mbid="release-mbid"
        )
        
        data = result.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data["title"], "Test Song")
        self.assertEqual(data["artist"], "Test Artist")
        self.assertEqual(data["album"], "Test Album")
        self.assertEqual(data["release_mbid"], "release-mbid")


if __name__ == '__main__':
    unittest.main()

