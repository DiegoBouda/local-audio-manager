import logging
from pathlib import Path
from typing import List, Tuple, Optional
from app.services.db_service import DBService

logger = logging.getLogger(__name__)


class PlaylistService:
    """Service for managing playlists."""
    
    def __init__(self, db_service: DBService):
        self.db = db_service
    
    def create_playlist(self, name: str) -> Optional[int]:
        """Create a new playlist. Returns playlist ID or None if name exists."""
        with self.db.lock:
            try:
                c = self.db.conn.cursor()
                c.execute('INSERT INTO playlists (name) VALUES (?)', (name,))
                self.db.conn.commit()
                playlist_id = c.lastrowid
                logger.info(f"Created playlist: {name} (ID: {playlist_id})")
                return playlist_id
            except Exception as e:
                logger.error(f"Failed to create playlist {name}: {e}")
                return None
    
    def delete_playlist(self, playlist_id: int):
        """Delete a playlist and all its tracks."""
        with self.db.lock:
            try:
                c = self.db.conn.cursor()
                c.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
                self.db.conn.commit()
                logger.info(f"Deleted playlist ID: {playlist_id}")
            except Exception as e:
                logger.error(f"Failed to delete playlist {playlist_id}: {e}")
    
    def rename_playlist(self, playlist_id: int, new_name: str) -> bool:
        """Rename a playlist. Returns True if successful."""
        with self.db.lock:
            try:
                c = self.db.conn.cursor()
                c.execute('UPDATE playlists SET name = ? WHERE id = ?', (new_name, playlist_id))
                self.db.conn.commit()
                logger.info(f"Renamed playlist {playlist_id} to {new_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to rename playlist {playlist_id}: {e}")
                return False
    
    def get_all_playlists(self) -> List[Tuple[int, str]]:
        """Get all playlists as (id, name) tuples."""
        with self.db.lock:
            c = self.db.conn.cursor()
            c.execute('SELECT id, name FROM playlists ORDER BY name')
            return c.fetchall()
    
    def get_playlist(self, playlist_id: int) -> Optional[Tuple[int, str]]:
        """Get a playlist by ID. Returns (id, name) or None."""
        with self.db.lock:
            c = self.db.conn.cursor()
            c.execute('SELECT id, name FROM playlists WHERE id = ?', (playlist_id,))
            return c.fetchone()
    
    def add_track_to_playlist(self, playlist_id: int, track_id: int):
        """Add a track to a playlist at the end."""
        with self.db.lock:
            try:
                # Get current max position
                c = self.db.conn.cursor()
                c.execute('''
                    SELECT MAX(position) FROM playlist_tracks 
                    WHERE playlist_id = ?
                ''', (playlist_id,))
                result = c.fetchone()
                next_position = (result[0] + 1) if result[0] is not None else 0
                
                # Insert track
                c.execute('''
                    INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position)
                    VALUES (?, ?, ?)
                ''', (playlist_id, track_id, next_position))
                self.db.conn.commit()
                logger.debug(f"Added track {track_id} to playlist {playlist_id} at position {next_position}")
            except Exception as e:
                logger.error(f"Failed to add track {track_id} to playlist {playlist_id}: {e}")
    
    def remove_track_from_playlist(self, playlist_id: int, track_id: int):
        """Remove a track from a playlist."""
        with self.db.lock:
            try:
                c = self.db.conn.cursor()
                c.execute('''
                    DELETE FROM playlist_tracks 
                    WHERE playlist_id = ? AND track_id = ?
                ''', (playlist_id, track_id))
                self.db.conn.commit()
                
                # Reorder remaining tracks
                self._reorder_playlist_tracks(playlist_id)
                logger.debug(f"Removed track {track_id} from playlist {playlist_id}")
            except Exception as e:
                logger.error(f"Failed to remove track {track_id} from playlist {playlist_id}: {e}")
    
    def get_playlist_tracks(self, playlist_id: int) -> List[Tuple]:
        """Get all tracks in a playlist, ordered by position.
        Returns list of track tuples (id, path, title, artist, album, duration).
        """
        with self.db.lock:
            c = self.db.conn.cursor()
            c.execute('''
                SELECT t.id, t.path, t.title, t.artist, t.album, t.duration
                FROM tracks t
                INNER JOIN playlist_tracks pt ON t.id = pt.track_id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            ''', (playlist_id,))
            return c.fetchall()
    
    def reorder_track_in_playlist(self, playlist_id: int, track_id: int, new_position: int):
        """Move a track to a new position in the playlist."""
        with self.db.lock:
            try:
                c = self.db.conn.cursor()
                
                # Get current position
                c.execute('''
                    SELECT position FROM playlist_tracks
                    WHERE playlist_id = ? AND track_id = ?
                ''', (playlist_id, track_id))
                result = c.fetchone()
                if not result:
                    return
                
                old_position = result[0]
                
                if old_position == new_position:
                    return
                
                # Shift other tracks
                if old_position < new_position:
                    # Moving down: shift tracks between old and new up
                    c.execute('''
                        UPDATE playlist_tracks
                        SET position = position - 1
                        WHERE playlist_id = ? AND position > ? AND position <= ?
                    ''', (playlist_id, old_position, new_position))
                else:
                    # Moving up: shift tracks between new and old down
                    c.execute('''
                        UPDATE playlist_tracks
                        SET position = position + 1
                        WHERE playlist_id = ? AND position >= ? AND position < ?
                    ''', (playlist_id, new_position, old_position))
                
                # Update the moved track's position
                c.execute('''
                    UPDATE playlist_tracks
                    SET position = ?
                    WHERE playlist_id = ? AND track_id = ?
                ''', (new_position, playlist_id, track_id))
                
                self.db.conn.commit()
                logger.debug(f"Moved track {track_id} in playlist {playlist_id} from {old_position} to {new_position}")
            except Exception as e:
                logger.error(f"Failed to reorder track in playlist: {e}")
    
    def _reorder_playlist_tracks(self, playlist_id: int):
        """Re-number positions to be sequential starting from 0."""
        with self.db.lock:
            try:
                c = self.db.conn.cursor()
                # Get all track positions in order
                c.execute('''
                    SELECT track_id FROM playlist_tracks
                    WHERE playlist_id = ?
                    ORDER BY position
                ''', (playlist_id,))
                tracks = c.fetchall()
                
                # Update positions sequentially
                for index, (track_id,) in enumerate(tracks):
                    c.execute('''
                        UPDATE playlist_tracks
                        SET position = ?
                        WHERE playlist_id = ? AND track_id = ?
                    ''', (index, playlist_id, track_id))
                
                self.db.conn.commit()
            except Exception as e:
                logger.error(f"Failed to reorder playlist tracks: {e}")
    
    def get_track_id_by_path(self, track_path: str) -> Optional[int]:
        """Get track ID by file path."""
        with self.db.lock:
            c = self.db.conn.cursor()
            c.execute('SELECT id FROM tracks WHERE path = ?', (track_path,))
            result = c.fetchone()
            return result[0] if result else None

