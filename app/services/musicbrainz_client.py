import logging
import time
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# MusicBrainz API configuration
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"
COVERART_API_URL = "https://coverartarchive.org"
USER_AGENT = "LocalAudioManager/1.0 (https://github.com/user/local-audio-manager)"

# Rate limiting: MusicBrainz allows 1 request per second
RATE_LIMIT_DELAY = 1.0  # seconds between requests


class MusicBrainzClient:
    """Client for MusicBrainz API - handles HTTP requests and rate limiting only."""
    
    def __init__(self):
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def search_recording(self, artist: str, title: str, limit: int = 10) -> Optional[Dict]:
        """Search for a recording on MusicBrainz.
        
        Args:
            artist: Artist name
            title: Track title
            limit: Maximum number of results to return
        
        Returns:
            Raw JSON response from API, or None on error
        """
        if not artist or not title:
            return None
        
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
                "limit": limit,
                "fmt": "json"
            }
            
            response = self.session.get(
                f"{MUSICBRAINZ_API_URL}/recording",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"MusicBrainz API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching MusicBrainz: {e}")
            return None
    
    def get_cover_art_metadata(self, release_mbid: str) -> Optional[Dict]:
        """Get cover art metadata from Cover Art Archive.
        
        Args:
            release_mbid: MusicBrainz release ID
        
        Returns:
            Raw JSON response from Cover Art Archive, or None on error
        """
        if not release_mbid:
            return None
        
        try:
            self._rate_limit()
            
            response = self.session.get(
                f"{COVERART_API_URL}/release/{release_mbid}",
                timeout=10
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.debug(f"Cover Art Archive error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching cover art: {e}")
            return None
    
    def download_image(self, image_url: str, save_path) -> bool:
        """Download an image file.
        
        Args:
            image_url: URL to the image
            save_path: Path to save the image
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(image_url, timeout=30, stream=True)
            response.raise_for_status()
            
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded image to {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return False

