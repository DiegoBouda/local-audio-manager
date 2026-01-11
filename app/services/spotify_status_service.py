import logging
from pathlib import Path
from typing import Dict, List
from mutagen import File

from app.helpers.audio_helpers import is_supported_audio, is_visible_to_spotify

logger = logging.getLogger(__name__)


class SpotifyStatusService:
    """Service for analyzing why tracks aren't visible in Spotify."""
    
    def __init__(self, config_service):
        self.config = config_service
    
    def analyze_track(self, track_path: str) -> Dict:
        """Analyze a track and return detailed status information.
        
        Args:
            track_path: Path to the track file
        
        Returns:
            Dictionary with status information and issues found
        """
        file_path = Path(track_path)
        
        status = {
            "path": track_path,
            "filename": file_path.name,
            "is_spotify_ready": True,
            "issues": [],
            "checks": {
                "file_exists": False,
                "supported_format": False,
                "in_spotify_folder": False,
                "has_read_permission": False,
                "metadata_valid": False
            },
            "details": {}
        }
        
        # Check 1: File exists
        if not file_path.exists():
            status["is_spotify_ready"] = False
            status["issues"].append("File does not exist")
            status["checks"]["file_exists"] = False
            status["details"]["file_exists"] = "File not found at this location"
            return status
        
        status["checks"]["file_exists"] = True
        status["details"]["file_exists"] = "File exists"
        
        # Check 2: Supported format
        if not is_supported_audio(file_path):
            status["is_spotify_ready"] = False
            status["issues"].append("Unsupported format")
            status["checks"]["supported_format"] = False
            status["details"]["supported_format"] = f"Format '{file_path.suffix}' is not supported (MP3, WAV, FLAC only)"
        else:
            status["checks"]["supported_format"] = True
            status["details"]["supported_format"] = f"Format '{file_path.suffix}' is supported"
        
        # Check 3: In Spotify-visible folder
        spotify_folders = [Path(p) for p in self.config.get_spotify_folders()]
        if not spotify_folders:
            status["is_spotify_ready"] = False
            status["issues"].append("No Spotify folder configured")
            status["checks"]["in_spotify_folder"] = False
            status["details"]["in_spotify_folder"] = "No Spotify-visible folder has been set"
        elif not is_visible_to_spotify(file_path, spotify_folders):
            status["is_spotify_ready"] = False
            status["issues"].append("Outside Spotify scan path")
            status["checks"]["in_spotify_folder"] = False
            status["details"]["in_spotify_folder"] = f"File is not in any configured Spotify folder:\n" + "\n".join(f"  • {f}" for f in spotify_folders)
        else:
            status["checks"]["in_spotify_folder"] = True
            # Find which folder
            for folder in spotify_folders:
                try:
                    file_path.resolve().relative_to(folder.resolve())
                    status["details"]["in_spotify_folder"] = f"File is in Spotify folder: {folder}"
                    break
                except ValueError:
                    continue
        
        # Check 4: Read permissions
        try:
            if not file_path.is_file():
                status["is_spotify_ready"] = False
                status["issues"].append("Not a file")
                status["checks"]["has_read_permission"] = False
                status["details"]["has_read_permission"] = "Path is not a file"
            elif not file_path.stat().st_mode & 0o444:  # Check read permission
                status["is_spotify_ready"] = False
                status["issues"].append("Missing read permission")
                status["checks"]["has_read_permission"] = False
                status["details"]["has_read_permission"] = "File does not have read permissions"
            else:
                status["checks"]["has_read_permission"] = True
                status["details"]["has_read_permission"] = "File has read permissions"
        except PermissionError:
            status["is_spotify_ready"] = False
            status["issues"].append("Missing permissions")
            status["checks"]["has_read_permission"] = False
            status["details"]["has_read_permission"] = "Cannot access file - permission denied"
        except Exception as e:
            status["is_spotify_ready"] = False
            status["issues"].append("Permission error")
            status["checks"]["has_read_permission"] = False
            status["details"]["has_read_permission"] = f"Error checking permissions: {e}"
        
        # Check 5: Metadata validity
        try:
            audio = File(str(file_path), easy=True)
            if not audio:
                status["is_spotify_ready"] = False
                status["issues"].append("Broken metadata")
                status["checks"]["metadata_valid"] = False
                status["details"]["metadata_valid"] = "Cannot read audio file metadata"
            else:
                # Check if basic metadata exists
                has_title = bool(audio.get("title"))
                has_artist = bool(audio.get("artist"))
                
                if not has_title and not has_artist:
                    status["details"]["metadata_valid"] = "Metadata exists but is incomplete (no title or artist)"
                else:
                    status["checks"]["metadata_valid"] = True
                    status["details"]["metadata_valid"] = "Metadata is readable"
                    
                    # Show what metadata exists
                    metadata_info = []
                    if has_title:
                        metadata_info.append(f"Title: {audio.get('title', [''])[0]}")
                    if has_artist:
                        metadata_info.append(f"Artist: {audio.get('artist', [''])[0]}")
                    if audio.get("album"):
                        metadata_info.append(f"Album: {audio.get('album', [''])[0]}")
                    
                    status["details"]["metadata_content"] = "\n".join(metadata_info)
        except Exception as e:
            logger.debug(f"Error reading metadata for {file_path}: {e}")
            # Don't fail Spotify readiness just because metadata read fails
            # Some files might be valid even if metadata read fails
            status["details"]["metadata_valid"] = f"Warning: Could not read metadata ({type(e).__name__})"
        
        return status
    
    def get_fix_suggestions(self, status: Dict) -> List[str]:
        """Get suggestions for fixing issues.
        
        Args:
            status: Status dictionary from analyze_track
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        if not status["checks"]["file_exists"]:
            suggestions.append("• File has been moved or deleted - remove from library")
        
        if not status["checks"]["supported_format"]:
            suggestions.append("• Convert file to MP3, WAV, or FLAC format")
            suggestions.append("• Use a media converter to change the file format")
        
        if not status["checks"]["in_spotify_folder"]:
            spotify_folders = self.config.get_spotify_folders()
            if not spotify_folders:
                suggestions.append("• Set a Spotify-visible folder in settings")
                suggestions.append("• Copy or move files to the Spotify folder after setting it")
            else:
                suggestions.append("• Move file to one of these Spotify folders:")
                for folder in spotify_folders:
                    suggestions.append(f"  - {folder}")
        
        if not status["checks"]["has_read_permission"]:
            suggestions.append("• Fix file permissions (chmod +r on Unix/Mac)")
            suggestions.append("• Check file ownership")
            suggestions.append("• Move file to a location with proper permissions")
        
        if "Broken metadata" in status["issues"]:
            suggestions.append("• File may be corrupted - try re-encoding")
            suggestions.append("• Use metadata editor to fix file tags")
        
        if status["is_spotify_ready"] and len(suggestions) == 0:
            suggestions.append("✓ Track appears to be ready for Spotify!")
            suggestions.append("• Make sure Spotify is configured to scan local files")
            suggestions.append("• Check Spotify's local files folder in settings")
        
        return suggestions

