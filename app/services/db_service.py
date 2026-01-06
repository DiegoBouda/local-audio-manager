import sqlite3
from pathlib import Path

class DBService:
    def __init__(self):
        self.db_dir = Path.home() / ".local_audio_manager"
        self.db_file = self.db_dir / "audio_library.db"
        self.db_dir.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(self.db_file)
        self._create_tables()

    def _create_tables(self):
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
        c = self.conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO tracks (path, title, artist, album, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (path, title, artist, album, duration))
        self.conn.commit()

    def get_all_tracks(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM tracks")
        return c.fetchall()