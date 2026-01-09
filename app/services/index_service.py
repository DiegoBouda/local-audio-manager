import logging
from pathlib import Path
from mutagen import File
from app.services.db_service import DBService
from app.helpers.audio_helpers import is_supported_audio

logger = logging.getLogger(__name__)

class IndexService:
    def __init__(self, db_service: DBService):
        self.db = db_service

    def scan_folder(self, folder_path: str):
        folder = Path(folder_path)
        if not folder.is_dir():
            return

        for file_path in folder.rglob("*"):
            if is_supported_audio(file_path):
                self._process_file(file_path)

    def _process_file(self, file_path: Path):
        try:
            # Check if file exists and is readable
            if not file_path.exists():
                logger.debug(f"File does not exist: {file_path}")
                return
            
            audio = File(str(file_path), easy=True)

            title = audio.get("title", [""])[0] if audio else ""
            artist = audio.get("artist", [""])[0] if audio else ""
            album = audio.get("album", [""])[0] if audio else ""
            duration = audio.info.length if audio and hasattr(audio, "info") else 0

            self.db.add_track(
                str(file_path),
                title,
                artist,
                album,
                duration
            )
        except Exception as e:
            # Reduce log noise for common "file not ready" errors during downloads
            error_msg = str(e).lower()
            if 'can\'t sync' in error_msg or 'no such file' in error_msg or 'permission denied' in error_msg:
                logger.debug(f"File not ready for reading (will retry): {file_path.name}")
            else:
                logger.error(f"Failed to read {file_path}: {e}")