import logging
from pathlib import Path
from typing import List, Tuple
from urllib.parse import quote
from app.services.playlist_service import PlaylistService

logger = logging.getLogger(__name__)


class M3UService:
    """Service for exporting playlists to M3U format."""
    
    def __init__(self, playlist_service: PlaylistService):
        self.playlist_service = playlist_service
    
    def export_playlist_to_m3u(self, playlist_id: int, output_path: Path, use_relative_paths: bool = False) -> bool:
        """Export a playlist to M3U format.
        
        Args:
            playlist_id: ID of the playlist to export
            output_path: Path where the M3U file should be saved
            use_relative_paths: If True, use relative paths from M3U file location
        
        Returns:
            True if successful, False otherwise
        """
        try:
            playlist = self.playlist_service.get_playlist(playlist_id)
            if not playlist:
                logger.error(f"Playlist {playlist_id} not found")
                return False
            
            _, playlist_name = playlist  # playlist is (id, name)
            tracks = self.playlist_service.get_playlist_tracks(playlist_id)
            
            if not tracks:
                logger.warning(f"Playlist {playlist_name} is empty, creating empty M3U file")
            
            # Determine base path for relative paths
            base_path = output_path.parent if use_relative_paths else None
            
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write M3U header
                f.write('#EXTM3U\n')
                
                # Write each track
                for track in tracks:
                    track_id, track_path, title, artist, album, duration = track
                    
                    # Format duration as seconds (M3U uses seconds, not float)
                    duration_seconds = int(duration) if duration else 0
                    
                    # Format track info
                    display_title = title or Path(track_path).stem
                    display_artist = artist or "Unknown Artist"
                    
                    # Write extended info line
                    f.write(f'#EXTINF:{duration_seconds},{display_artist} - {display_title}\n')
                    
                    # Write file path
                    file_path = Path(track_path)
                    
                    if use_relative_paths and base_path:
                        try:
                            # Get relative path from M3U file to track
                            rel_path = file_path.relative_to(base_path)
                            # Use forward slashes (M3U standard) and URL encode
                            rel_path_str = str(rel_path).replace('\\', '/')
                            f.write(f'{rel_path_str}\n')
                        except ValueError:
                            # If path is not relative, use absolute
                            f.write(f'{file_path.as_uri()}\n')
                    else:
                        # Use absolute path with file:// protocol
                        f.write(f'{file_path.as_uri()}\n')
            
            logger.info(f"Exported playlist {playlist_name} to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export playlist to M3U: {e}")
            return False
    
    def import_playlist_from_m3u(self, m3u_path: Path, playlist_name: str) -> bool:
        """Import a playlist from an M3U file.
        
        Args:
            m3u_path: Path to the M3U file
            playlist_name: Name for the new playlist
        
        Returns:
            True if successful, False otherwise
        """
        try:
            playlist_id = self.playlist_service.create_playlist(playlist_name)
            if not playlist_id:
                logger.error(f"Failed to create playlist: {playlist_name}")
                return False
            
            base_path = m3u_path.parent
            
            with open(m3u_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse M3U file
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Handle file:// URLs and regular paths
                if line.startswith('file://'):
                    from urllib.parse import unquote
                    track_path = unquote(line[7:])  # Remove 'file://' prefix
                else:
                    track_path = line
                
                # Resolve relative paths
                track_path_obj = Path(track_path)
                if not track_path_obj.is_absolute():
                    track_path_obj = base_path / track_path_obj
                
                # Get track ID
                track_id = self.playlist_service.get_track_id_by_path(str(track_path_obj.resolve()))
                if track_id:
                    self.playlist_service.add_track_to_playlist(playlist_id, track_id)
                else:
                    logger.warning(f"Track not found in library: {track_path_obj}")
            
            logger.info(f"Imported playlist from {m3u_path} as {playlist_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import playlist from M3U: {e}")
            return False

