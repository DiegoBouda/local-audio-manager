import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Set
from collections import defaultdict

from app.services.db_service import DBService

logger = logging.getLogger(__name__)


class DuplicateService:
    """Service for detecting duplicate audio tracks."""
    
    def __init__(self, db_service: DBService):
        self.db = db_service
    
    def find_duplicates_by_filename(self) -> Dict[str, List[Tuple]]:
        """Find duplicates by filename (case-insensitive).
        
        Returns:
            Dictionary mapping filename to list of track tuples
        """
        tracks = self.db.get_all_tracks()
        filename_groups = defaultdict(list)
        
        for track in tracks:
            track_id, path, title, artist, album, genre, year, duration = track
            filename = Path(path).name.lower()
            filename_groups[filename].append(track)
        
        # Filter to only groups with more than one track
        duplicates = {filename: tracks for filename, tracks in filename_groups.items() 
                     if len(tracks) > 1}
        
        logger.info(f"Found {len(duplicates)} duplicate groups by filename")
        return duplicates
    
    def find_duplicates_by_hash(self, hash_size_mb: int = 1) -> Dict[str, List[Tuple]]:
        """Find duplicates by file content hash.
        
        Args:
            hash_size_mb: Size of file chunk to hash (in MB) for speed
        
        Returns:
            Dictionary mapping hash to list of track tuples
        """
        tracks = self.db.get_all_tracks()
        hash_groups = defaultdict(list)
        
        for track in tracks:
            track_id, path, title, artist, album, genre, year, duration = track
            file_path = Path(path)
            
            if not file_path.exists():
                continue
            
            try:
                file_hash = self._compute_file_hash(file_path, hash_size_mb)
                hash_groups[file_hash].append(track)
            except Exception as e:
                logger.debug(f"Failed to hash {path}: {e}")
                continue
        
        # Filter to only groups with more than one track
        duplicates = {file_hash: tracks for file_hash, tracks in hash_groups.items() 
                     if len(tracks) > 1}
        
        logger.info(f"Found {len(duplicates)} duplicate groups by hash")
        return duplicates
    
    def find_duplicates_by_metadata(self) -> Dict[str, List[Tuple]]:
        """Find duplicates by metadata (title, artist, album, duration).
        
        Returns:
            Dictionary mapping metadata key to list of track tuples
        """
        tracks = self.db.get_all_tracks()
        metadata_groups = defaultdict(list)
        
        for track in tracks:
            track_id, path, title, artist, album, genre, year, duration = track
            
            # Normalize metadata for comparison
            title_norm = (title or "").lower().strip()
            artist_norm = (artist or "").lower().strip()
            album_norm = (album or "").lower().strip()
            
            # Create metadata key (skip if all are empty)
            if title_norm or artist_norm:
                # Use duration within 1 second tolerance
                duration_key = int(duration) if duration else 0
                metadata_key = f"{artist_norm}|{title_norm}|{album_norm}|{duration_key}"
                metadata_groups[metadata_key].append(track)
        
        # Filter to only groups with more than one track
        duplicates = {metadata_key: tracks for metadata_key, tracks in metadata_groups.items() 
                     if len(tracks) > 1}
        
        logger.info(f"Found {len(duplicates)} duplicate groups by metadata")
        return duplicates
    
    def _compute_file_hash(self, file_path: Path, chunk_size_mb: int = 1) -> str:
        """Compute hash of file content.
        
        Uses first and last chunk for speed, or full file if small.
        """
        chunk_size = chunk_size_mb * 1024 * 1024  # Convert MB to bytes
        file_size = file_path.stat().st_size
        
        hash_obj = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            # For small files, hash the whole thing
            if file_size <= chunk_size * 2:
                hash_obj.update(f.read())
            else:
                # Hash first chunk
                hash_obj.update(f.read(chunk_size))
                # Hash last chunk
                f.seek(-chunk_size, 2)  # Seek to last chunk
                hash_obj.update(f.read())
                # Also include file size in hash
                hash_obj.update(str(file_size).encode())
        
        return hash_obj.hexdigest()
    
    def merge_duplicates(self, tracks_to_keep: Tuple, tracks_to_remove: List[Tuple]) -> int:
        """Merge duplicate tracks by keeping one and removing others from database.
        
        Args:
            tracks_to_keep: Track tuple to keep
            tracks_to_remove: List of track tuples to remove from database
        
        Returns:
            Number of tracks removed
        """
        removed_count = 0
        
        for track in tracks_to_remove:
            track_id, path, title, artist, album, genre, year, duration = track
            try:
                self.db.delete_track(path)
                removed_count += 1
            except Exception as e:
                logger.error(f"Failed to remove duplicate track {path}: {e}")
        
        logger.info(f"Merged {removed_count} duplicate tracks")
        return removed_count
    
    def delete_duplicates(self, tracks_to_delete: List[Tuple], delete_files: bool = False) -> int:
        """Delete duplicate tracks from database (and optionally from filesystem).
        
        Args:
            tracks_to_delete: List of track tuples to delete
            delete_files: If True, also delete files from filesystem
        
        Returns:
            Number of tracks deleted
        """
        deleted_count = 0
        
        for track in tracks_to_delete:
            track_id, path, title, artist, album, genre, year, duration = track
            file_path = Path(path)
            
            try:
                # Delete from database
                self.db.delete_track(path)
                deleted_count += 1
                
                # Optionally delete file
                if delete_files and file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted file: {file_path}")
            
            except Exception as e:
                logger.error(f"Failed to delete duplicate track {path}: {e}")
        
        logger.info(f"Deleted {deleted_count} duplicate tracks")
        return deleted_count
    
    def get_duplicate_summary(self) -> Dict[str, int]:
        """Get summary of duplicate counts by detection method.
        
        Returns:
            Dictionary with counts for each detection method
        """
        return {
            "by_filename": len(self.find_duplicates_by_filename()),
            "by_hash": len(self.find_duplicates_by_hash()),
            "by_metadata": len(self.find_duplicates_by_metadata())
        }

