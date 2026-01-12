import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MetadataMatch:
    """Result from metadata matching."""
    title: str
    artist: str
    album: Optional[str] = None
    release_mbid: Optional[str] = None
    cover_art_url: Optional[str] = None
    confidence: float = 1.0  # 0.0 to 1.0


class MetadataMatcher:
    """Matches and scores metadata results from MusicBrainz."""
    
    def find_best_match(self, recordings: List[Dict], artist: str, title: str, 
                       duration: Optional[float] = None) -> Optional[MetadataMatch]:
        """Find the best matching recording from a list.
        
        Args:
            recordings: List of recording dicts from MusicBrainz API
            artist: Expected artist name
            title: Expected title
            duration: Track duration in seconds (optional)
        
        Returns:
            Best matching MetadataMatch, or None if no good match
        """
        if not recordings:
            return None
        
        # MusicBrainz search already sorts by relevance, so try first result
        first_result = recordings[0]
        match = self._extract_match(first_result)
        
        # Check if first result matches duration (if provided)
        if duration and self._duration_matches(first_result, duration):
            # High confidence - duration matches
            match.confidence = 1.0
            return match
        
        # If duration provided but doesn't match, try to find a better match
        if duration:
            duration_match = self._match_by_duration(recordings, duration)
            if duration_match:
                match = self._extract_match(duration_match)
                match.confidence = 0.8  # Good match, but not perfect
                return match
            
            # Duration doesn't match any result - lower confidence
            match.confidence = 0.5
        else:
            # No duration to verify - medium confidence
            match.confidence = 0.7
        
        return match
    
    def _duration_matches(self, recording: Dict, target_duration: float) -> bool:
        """Check if recording duration matches target (within tolerance).
        
        Args:
            recording: Recording dict from API
            target_duration: Target duration in seconds
        
        Returns:
            True if duration matches within tolerance
        """
        length_ms = recording.get("length")
        if not length_ms:
            return False
        
        # Tolerance: ±5 seconds (5000ms)
        tolerance_ms = 5000
        target_ms = int(target_duration * 1000)
        
        return abs(length_ms - target_ms) <= tolerance_ms
    
    def _match_by_duration(self, recordings: List[Dict], target_duration: float) -> Optional[Dict]:
        """Find best matching recording by duration.
        
        Args:
            recordings: List of recording dicts
            target_duration: Target duration in seconds
        
        Returns:
            Best matching recording or None
        """
        tolerance_ms = 5000
        target_ms = int(target_duration * 1000)
        
        best_match = None
        best_diff = float('inf')
        
        for recording in recordings:
            length_ms = recording.get("length")
            if not length_ms:
                continue
            
            diff = abs(length_ms - target_ms)
            if diff <= tolerance_ms and diff < best_diff:
                best_diff = diff
                best_match = recording
        
        return best_match
    
    def _extract_match(self, recording: Dict) -> MetadataMatch:
        """Extract metadata from a MusicBrainz recording response."""
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
        release_mbid = None
        
        if releases:
            first_release = releases[0]
            album = first_release.get("title")
            release_mbid = first_release.get("id")
        
        return MetadataMatch(
            title=title,
            artist=artist,
            album=album,
            release_mbid=release_mbid
        )
    
    def extract_cover_art_url(self, cover_art_data: Dict) -> Optional[str]:
        """Extract cover art URL from Cover Art Archive response.
        
        Args:
            cover_art_data: JSON response from Cover Art Archive
        
        Returns:
            URL to cover art image, or None if not found
        """
        images = cover_art_data.get("images", [])
        
        # Get front cover
        for image in images:
            if image.get("front", False):
                return image.get("image")
        
        # Fallback to first image
        if images:
            return images[0].get("image")
        
        return None

