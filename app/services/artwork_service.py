import logging
from pathlib import Path
from typing import Optional
from app.services.metadata_service import MetadataService

logger = logging.getLogger(__name__)


class ArtworkService:
    """Service for managing artwork for tracks."""
    
    def __init__(self):
        self.artwork_dir = Path.home() / ".local_audio_manager" / "artwork"
        self.metadata_service = MetadataService()
    
    def has_embedded_artwork(self, file_path: Path) -> bool:
        """Check if file has embedded artwork."""
        try:
            metadata = self.metadata_service.get_metadata(file_path)
            return metadata.get("artwork") is not None
        except:
            return False
    
    def has_local_artwork(self, file_path: Path) -> Optional[Path]:
        """Check if local artwork file exists for this track.
        
        Returns:
            Path to artwork file if found, None otherwise
        """
        # Check for artwork by release MBID or track name
        artwork_dir = self.artwork_dir
        
        if not artwork_dir.exists():
            return None
        
        # Try various naming patterns
        patterns = [
            f"{file_path.stem}.jpg",
            f"{file_path.stem}.png",
            f"{file_path.stem}.jpeg"
        ]
        
        for pattern in patterns:
            artwork_path = artwork_dir / pattern
            if artwork_path.exists():
                return artwork_path
        
        return None
    
    def get_artwork_status(self, file_path: Path) -> str:
        """Get artwork status for display.
        
        Returns:
            "[Artwork Missing]", "[Artwork Found]", or "[Embedded Artwork]"
        """
        if self.has_embedded_artwork(file_path):
            return "[Embedded Artwork]"
        
        if self.has_local_artwork(file_path):
            return "[Artwork Found]"
        
        return "[Artwork Missing]"

