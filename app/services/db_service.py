import sqlite3
import threading
from pathlib import Path

class DBService:
    def __init__(self):
        self.db_dir = Path.home() / ".local_audio_manager"
        self.db_file = self.db_dir / "audio_library.db"
        self.db_dir.mkdir(exist_ok=True)
        # Allow cross-thread access with proper locking
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self._create_tables()

    def _create_tables(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY,
                    path TEXT UNIQUE,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    duration REAL
                )
            ''')
            self.conn.commit()

    def add_track(self, path, title="", artist="", album="", duration=0):
        with self.lock:
            c = self.conn.cursor()
            c.execute('''
                INSERT OR IGNORE INTO tracks (path, title, artist, album, duration)
                VALUES (?, ?, ?, ?, ?)
            ''', (path, title, artist, album, duration))
            self.conn.commit()

    def get_all_tracks(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute("SELECT * FROM tracks")
            return c.fetchall()
    
    def delete_track(self, path: str):
        """Remove a track from the database by path."""
        with self.lock:
            c = self.conn.cursor()
            c.execute("DELETE FROM tracks WHERE path = ?", (path,))
            self.conn.commit()
    
    def track_exists(self, path: str) -> bool:
        """Check if a track exists in the database."""
        with self.lock:
            c = self.conn.cursor()
            c.execute("SELECT 1 FROM tracks WHERE path = ?", (path,))
            return c.fetchone() is not None