import logging
import threading
import time
from pathlib import Path
from collections import defaultdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileMovedEvent
from PySide6.QtCore import QObject, Signal

from app.services.index_service import IndexService
from app.services.db_service import DBService
from app.helpers.audio_helpers import is_supported_audio

logger = logging.getLogger(__name__)

# Temporary file extensions to ignore (browser downloads)
TEMP_EXTENSIONS = {'.part', '.crdownload', '.tmp', '.download', '.!qB'}


class AudioFileHandler(FileSystemEventHandler):
    """Handles file system events for audio files."""
    
    def __init__(self, index_service: IndexService, db_service: DBService, update_signal: Signal):
        super().__init__()
        self.index_service = index_service
        self.db_service = db_service
        self.update_signal = update_signal
        self._debounce_delay = 2.0  # Wait 2s before processing to ensure file is fully written
        self._pending_files = {}  # Track files waiting to be processed
        self._pending_timers = {}  # Track active timers
        self._lock = threading.Lock()
        
    def _is_temp_file(self, path: Path) -> bool:
        """Check if file is a temporary download file."""
        return path.suffix.lower() in TEMP_EXTENSIONS or '.part' in path.name.lower()
    
    def _schedule_process(self, path: Path, event_type: str):
        """Schedule a file to be processed after debounce delay."""
        path_str = str(path)
        
        with self._lock:
            # Cancel existing timer for this file
            if path_str in self._pending_timers:
                self._pending_timers[path_str].cancel()
            
            # Create new timer
            def process_file():
                with self._lock:
                    if path_str in self._pending_files:
                        del self._pending_files[path_str]
                    if path_str in self._pending_timers:
                        del self._pending_timers[path_str]
                
                # Check if file still exists and is complete
                if not path.exists():
                    logger.debug(f"File no longer exists: {path}")
                    return
                
                # Check if file is still being written (size changed recently)
                try:
                    size1 = path.stat().st_size
                    time.sleep(0.5)
                    size2 = path.stat().st_size
                    if size1 != size2:
                        # File still being written, reschedule
                        logger.debug(f"File still being written, rescheduling: {path}")
                        self._schedule_process(path, event_type)
                        return
                except Exception:
                    pass
                
                # Process the file
                try:
                    logger.info(f"Processing {event_type} audio file: {path.name}")
                    self.index_service._process_file(path)
                    self.update_signal.emit()
                except Exception as e:
                    # Only log as error if it's not a common "file still being written" error
                    error_msg = str(e).lower()
                    if 'can\'t sync' in error_msg or 'no such file' in error_msg:
                        logger.debug(f"File not ready yet (will retry on next event): {path.name}")
                    else:
                        logger.error(f"Error processing file {path}: {e}")
            
            timer = threading.Timer(self._debounce_delay, process_file)
            self._pending_timers[path_str] = timer
            self._pending_files[path_str] = event_type
            timer.start()
        
    def on_created(self, event: FileSystemEvent):
        """Called when a file or directory is created."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Ignore temporary download files
        if self._is_temp_file(path):
            return
        
        if is_supported_audio(path):
            # Schedule processing after delay to ensure file is fully written
            self._schedule_process(path, "new")
    
    def on_deleted(self, event: FileSystemEvent):
        """Called when a file or directory is deleted."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if is_supported_audio(path):
            try:
                logger.info(f"Audio file deleted: {path}")
                self.db_service.delete_track(str(path))
                self.update_signal.emit()
            except Exception as e:
                logger.error(f"Error deleting track from database {path}: {e}")
    
    def on_modified(self, event: FileSystemEvent):
        """Called when a file or directory is modified."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Ignore temporary download files
        if self._is_temp_file(path):
            return
        
        if is_supported_audio(path) and path.exists():
            # Schedule processing with debounce to avoid multiple events during download
            self._schedule_process(path, "modified")
    
    def on_moved(self, event: FileMovedEvent):
        """Called when a file or directory is moved or renamed."""
        if event.is_directory:
            return
        
        # Handle file move/rename
        old_path = Path(event.src_path)
        new_path = Path(event.dest_path)
        
        # Ignore if moving from/to temporary files
        if self._is_temp_file(old_path) or self._is_temp_file(new_path):
            # If moving FROM temp file TO audio file, this is likely a completed download
            if self._is_temp_file(old_path) and is_supported_audio(new_path) and new_path.exists():
                logger.debug(f"Download completed (temp -> audio): {new_path.name}")
                self._schedule_process(new_path, "moved")
            return
        
        try:
            if is_supported_audio(new_path) and new_path.exists():
                # Cancel any pending processing for old path
                with self._lock:
                    old_path_str = str(old_path)
                    if old_path_str in self._pending_timers:
                        self._pending_timers[old_path_str].cancel()
                        if old_path_str in self._pending_files:
                            del self._pending_files[old_path_str]
                        del self._pending_timers[old_path_str]
                
                logger.info(f"Audio file moved/renamed: {old_path.name} -> {new_path.name}")
                # Delete old entry
                self.db_service.delete_track(str(old_path))
                # Schedule processing of new file
                self._schedule_process(new_path, "moved")
            elif is_supported_audio(old_path):
                # File was moved/renamed to non-audio location or deleted
                logger.info(f"Audio file moved/renamed to non-audio: {old_path.name}")
                self.db_service.delete_track(str(old_path))
                self.update_signal.emit()
        except Exception as e:
            logger.error(f"Error processing moved file {old_path} -> {new_path}: {e}")


class WatchService(QObject):
    """Service for monitoring file system changes in real-time."""
    
    # Signal emitted when library needs to be refreshed
    library_updated = Signal()
    
    def __init__(self, index_service: IndexService, db_service: DBService):
        super().__init__()
        self.index_service = index_service
        self.db_service = db_service
        self.observer = Observer()
        self.watched_paths = {}
        self.is_running = False
        
    def start_watching(self, folder_paths: list[str]):
        """Start watching the specified folders for changes."""
        if self.is_running:
            self.stop_watching()
        
        for folder_path in folder_paths:
            path = Path(folder_path)
            if not path.exists() or not path.is_dir():
                logger.warning(f"Cannot watch non-existent folder: {folder_path}")
                continue
            
            try:
                handler = AudioFileHandler(
                    self.index_service,
                    self.db_service,
                    self.library_updated
                )
                self.observer.schedule(handler, str(path), recursive=True)
                self.watched_paths[folder_path] = handler
                logger.info(f"Started watching: {folder_path}")
            except Exception as e:
                logger.error(f"Failed to watch folder {folder_path}: {e}")
        
        if self.watched_paths:
            self.observer.start()
            self.is_running = True
            logger.info("File system monitoring started")
    
    def stop_watching(self):
        """Stop watching all folders."""
        if self.is_running:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.watched_paths.clear()
            self.is_running = False
            logger.info("File system monitoring stopped")
    
    def add_folder(self, folder_path: str):
        """Add a new folder to watch."""
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            logger.warning(f"Cannot watch non-existent folder: {folder_path}")
            return
        
        if folder_path in self.watched_paths:
            logger.info(f"Folder already being watched: {folder_path}")
            return
        
        try:
            handler = AudioFileHandler(
                self.index_service,
                self.db_service,
                self.library_updated
            )
            self.observer.schedule(handler, str(path), recursive=True)
            self.watched_paths[folder_path] = handler
            
            if not self.is_running:
                self.observer.start()
                self.is_running = True
            
            logger.info(f"Added watch for folder: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to add watch for folder {folder_path}: {e}")
    
    def remove_folder(self, folder_path: str):
        """Remove a folder from watching."""
        # Note: watchdog doesn't support removing individual watches easily
        # So we'll stop and restart with the remaining folders
        if folder_path in self.watched_paths:
            current_folders = list(self.watched_paths.keys())
            current_folders.remove(folder_path)
            self.stop_watching()
            if current_folders:
                self.start_watching(current_folders)
            logger.info(f"Removed watch for folder: {folder_path}")

