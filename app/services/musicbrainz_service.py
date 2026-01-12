import logging
import time
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# MusicBrainz API configuration
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"
COVERART_API_URL = "https://coverartarchive.org"
USER_AGENT = "LocalAudioManager/1.0 (https://github.com/user/local-audio-manager)"

# Rate limiting: MusicBrainz allows 1 request per second
RATE_LIMIT_DELAY = 1.0  # seconds between requests
CACHE_DURATION_HOURS = 24  # Cache results for 24 hours


@dataclass
class MusicBrainzResult:
    """Result from MusicBrainz API."""
    title: str
    artist: str
    album: Optional[str] = None
    release_date: Optional[str] = None
    track_number: Optional[int] = None
    duration_ms: Optional[int] = None
    mbid: Optional[str] = None  # MusicBrainz ID
    release_mbid: Optional[str] = None
    cover_art_url: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "release_date": self.release_date,
            "track_number": self.track_number,
            "duration_ms": self.duration_ms,
            "mbid": self.mbid,
            "release_mbid": self.release_mbid,
            "cover_art_url": self.cover_art_url
        }


class MusicBrainzService:
    """Service for fetching metadata from MusicBrainz API."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".local_audio_manager" / "musicbrainz_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def _get_cache_key(self, artist: str, title: str, duration: Optional[float]) -> str:
        """Generate cache key from search parameters."""
        # Normalize for cache key
        artist_norm = artist.lower().strip()
        title_norm = title.lower().strip()
        duration_key = int(duration) if duration else 0
        return f"{artist_norm}|{title_norm}|{duration_key}"
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path."""
        # Use hash of key for filename
        import hashlib
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load result from cache."""
        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is still valid
            cache_time = datetime.fromisoformat(cache_data.get("cached_at", ""))
            if datetime.now() - cache_time > timedelta(hours=CACHE_DURATION_HOURS):
                cache_path.unlink()  # Remove expired cache
                return None
            
            return cache_data.get("result")
        except Exception as e:
            logger.debug(f"Error loading cache: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, result: Dict):
        """Save result to cache."""
        try:
            cache_path = self._get_cache_path(cache_key)
            cache_data = {
                "cached_at": datetime.now().isoformat(),
                "result": result
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.debug(f"Error saving cache: {e}")
    
    def search_track(self, artist: str, title: str, duration: Optional[float] = None) -> Optional[MusicBrainzResult]:
        """Search for a track on MusicBrainz.
        
        Args:
            artist: Artist name
            title: Track title
            duration: Track duration in seconds (optional, used for matching)
        
        Returns:
            MusicBrainzResult if found, None otherwise
        """
        if not artist or not title:
            return None
        
        # Check cache first
        cache_key = self._get_cache_key(artist, title, duration)
        cached_result = self._load_from_cache(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for: {artist} - {title}")
            return MusicBrainzResult(**cached_result) if cached_result else None
        
        # Apply rate limiting
        self._rate_limit()
        
        try:
            # Build query
            query_parts = []
            if artist:
                query_parts.append(f'artist:"{artist}"')
            if title:
                query_parts.append(f'recording:"{title}"')
            
            query = " AND ".join(query_parts)
            
            # Search MusicBrainz
            params = {
                "query": query,
                "limit": 10,
                "fmt": "json"
            }
            
            response = self.session.get(
                f"{MUSICBRAINZ_API_URL}/recording",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            recordings = data.get("recordings", [])
            
            if not recordings:
                self._save_to_cache(cache_key, {})  # Cache empty result
                return None
            
            # Match recordings by duration if provided
            duration_ms = int(duration * 1000) if duration else None
            best_match = self._match_by_duration(recordings, duration_ms)
            
            if not best_match:
                best_match = recordings[0]  # Use first result if no duration match
            
            # Extract data
            result = self._extract_recording_data(best_match)
            
            # Cache result
            self._save_to_cache(cache_key, result.to_dict())
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"MusicBrainz API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching MusicBrainz: {e}")
            return None
    
    def _match_by_duration(self, recordings: List[Dict], target_duration_ms: Optional[int]) -> Optional[Dict]:
        """Match recordings by duration with tolerance.
        
        Args:
            recordings: List of recording dicts from API
            target_duration_ms: Target duration in milliseconds
        
        Returns:
            Best matching recording or None
        """
        if not target_duration_ms:
            return None
        
        # Tolerance: ±5 seconds (5000ms)
        tolerance = 5000
        
        best_match = None
        best_diff = float('inf')
        
        for recording in recordings:
            length = recording.get("length")
            if not length:
                continue
            
            diff = abs(length - target_duration_ms)
            if diff <= tolerance and diff < best_diff:
                best_diff = diff
                best_match = recording
        
        return best_match
    
    def _extract_recording_data(self, recording: Dict) -> MusicBrainzResult:
        """Extract data from MusicBrainz recording response."""
        title = recording.get("title", "")
        
        # Get artist
        artist_credits = recording.get("artist-credit", [])
        if artist_credits:
            artist = artist_credits[0].get("artist", {}).get("name", "")
        else:
            artist = ""
        
        # Get release information (first release)
        releases = recording.get("releases", [])
        album = None
        release_date = None
        release_mbid = None
        track_number = None
        
        if releases:
            first_release = releases[0]
            album = first_release.get("title")
            release_date = first_release.get("date")
            release_mbid = first_release.get("id")
            
            # Get track number
            media = first_release.get("media", [])
            if media:
                tracks = media[0].get("tracks", [])
                for track in tracks:
                    if track.get("recording", {}).get("id") == recording.get("id"):
                        track_number = track.get("number")
                        break
        
        return MusicBrainzResult(
            title=title,
            artist=artist,
            album=album,
            release_date=release_date,
            track_number=track_number,
            duration_ms=recording.get("length"),
            mbid=recording.get("id"),
            release_mbid=release_mbid
        )
    
    def get_cover_art(self, release_mbid: str) -> Optional[str]:
        """Get cover art URL from Cover Art Archive.
        
        Args:
            release_mbid: MusicBrainz release ID
        
        Returns:
            URL to cover art image, or None if not found
        """
        if not release_mbid:
            return None
        
        try:
            # Apply rate limiting
            self._rate_limit()
            
            # Fetch from Cover Art Archive
            response = self.session.get(
                f"{COVERART_API_URL}/release/{release_mbid}",
                timeout=10
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Get front cover
            images = data.get("images", [])
            for image in images:
                if image.get("front", False):
                    return image.get("image")
            
            # Fallback to first image
            if images:
                return images[0].get("image")
            
            return None
            
        except requests.RequestException as e:
            logger.debug(f"Cover Art Archive error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching cover art: {e}")
            return None
    
    def download_cover_art(self, cover_art_url: str, save_path: Path) -> bool:
        """Download cover art image.
        
        Args:
            cover_art_url: URL to cover art image
            save_path: Path to save the image
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(cover_art_url, timeout=30, stream=True)
            response.raise_for_status()
            
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded cover art to {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading cover art: {e}")
            return False

