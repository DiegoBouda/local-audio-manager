from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QCheckBox,
    QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtGui import QPixmap, QImage
from pathlib import Path
from typing import Optional, Dict
import logging

from app.services.musicbrainz_service import MusicBrainzService, MusicBrainzResult

logger = logging.getLogger(__name__)


class MusicBrainzFetchThread(QThread):
    """Thread for fetching metadata from MusicBrainz."""
    finished = Signal(object)  # Emits MusicBrainzResult or None
    progress = Signal(str)
    
    def __init__(self, musicbrainz_service: MusicBrainzService, 
                 artist: str, title: str, duration: Optional[float] = None):
        super().__init__()
        self.musicbrainz_service = musicbrainz_service
        self.artist = artist
        self.title = title
        self.duration = duration
    
    def run(self):
        try:
            self.progress.emit("Searching MusicBrainz...")
            result = self.musicbrainz_service.search_track(
                self.artist,
                self.title,
                self.duration
            )
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Error in MusicBrainz fetch: {e}")
            self.finished.emit(None)


class MusicBrainzFetchDialog(QDialog):
    """Dialog for fetching and approving metadata from MusicBrainz."""
    
    def __init__(self, file_path: Path, current_metadata: Dict, 
                 musicbrainz_service: MusicBrainzService, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.current_metadata = current_metadata
        self.musicbrainz_service = musicbrainz_service
        self.fetched_result = None
        self.cover_art_url = None
        self.artwork_path = None
        self.should_fetch = True
        
        self.setWindowTitle("Fetch Metadata from MusicBrainz")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self._setup_ui()
        self._check_if_should_fetch()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Current metadata
        current_group = QGroupBox("Current Metadata")
        current_layout = QFormLayout(current_group)
        
        self.current_title = QLabel(self.current_metadata.get("title", "") or "(empty)")
        self.current_artist = QLabel(self.current_metadata.get("artist", "") or "(empty)")
        self.current_album = QLabel(self.current_metadata.get("album", "") or "(empty)")
        self.current_year = QLabel(str(self.current_metadata.get("year", "")) or "(empty)")
        
        current_layout.addRow("Title:", self.current_title)
        current_layout.addRow("Artist:", self.current_artist)
        current_layout.addRow("Album:", self.current_album)
        current_layout.addRow("Year:", self.current_year)
        
        layout.addWidget(current_group)
        
        # Fetched metadata
        fetched_group = QGroupBox("Fetched Metadata")
        fetched_layout = QVBoxLayout(fetched_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        fetched_layout.addWidget(self.progress_bar)
        
        fetched_form = QFormLayout()
        
        self.fetched_title = QLabel("(not fetched)")
        self.fetched_artist = QLabel("(not fetched)")
        self.fetched_album = QLabel("(not fetched)")
        
        fetched_form.addRow("Title:", self.fetched_title)
        fetched_form.addRow("Artist:", self.fetched_artist)
        fetched_form.addRow("Album:", self.fetched_album)
        
        fetched_layout.addLayout(fetched_form)
        
        # Checkboxes for fields to apply
        self.apply_title = QCheckBox("Apply Title")
        self.apply_artist = QCheckBox("Apply Artist")
        self.apply_album = QCheckBox("Apply Album")
        
        apply_layout = QVBoxLayout()
        apply_layout.addWidget(QLabel("Fields to apply:"))
        apply_layout.addWidget(self.apply_title)
        apply_layout.addWidget(self.apply_artist)
        apply_layout.addWidget(self.apply_album)
        
        fetched_layout.addLayout(apply_layout)
        
        layout.addWidget(fetched_group)
        
        # Cover art
        cover_group = QGroupBox("Album Artwork")
        cover_layout = QVBoxLayout(cover_group)
        
        self.cover_preview = QLabel("No artwork available")
        self.cover_preview.setMinimumHeight(150)
        self.cover_preview.setMaximumHeight(250)
        self.cover_preview.setAlignment(Qt.AlignCenter)
        self.cover_preview.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        
        cover_buttons = QHBoxLayout()
        self.download_artwork_button = QPushButton("Download Artwork")
        self.download_artwork_button.setEnabled(False)
        cover_buttons.addWidget(self.download_artwork_button)
        cover_buttons.addStretch()
        
        cover_layout.addWidget(self.cover_preview)
        cover_layout.addLayout(cover_buttons)
        
        layout.addWidget(cover_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._apply_metadata)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
        # Connect signals
        self.download_artwork_button.clicked.connect(self._download_artwork)
    
    def _check_if_should_fetch(self):
        """Check if fetch should proceed."""
        artist = self.current_metadata.get("artist", "") or ""
        title = self.current_metadata.get("title", "") or ""
        artist = artist.strip() if isinstance(artist, str) else ""
        title = title.strip() if isinstance(title, str) else ""
        
        # Only fetch if metadata is missing or suspicious
        needs_fetch = (
            not artist or 
            not title or 
            artist.lower() == "unknown artist" or 
            title.lower() == "unknown title" or
            artist == "" or
            title == ""
        )
        
        if not needs_fetch:
            # Still offer to fetch if user wants to update
            # Use QMessageBox directly, not as a child of self since self isn't shown yet
            reply = QMessageBox.question(
                None,  # Use None as parent so it appears as top-level
                "Metadata Already Present",
                "This track already has metadata. Fetch from MusicBrainz anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.should_fetch = False
                # Don't start fetch - the dialog won't be shown later
                return
        
        # Start fetch
        self._start_fetch()
    
    def _start_fetch(self):
        """Start fetching from MusicBrainz."""
        artist = self.current_metadata.get("artist", "").strip()
        title = self.current_metadata.get("title", "").strip()
        duration = self.current_metadata.get("duration")
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        self.fetch_thread = MusicBrainzFetchThread(
            self.musicbrainz_service,
            artist or "",
            title or "",
            duration
        )
        self.fetch_thread.finished.connect(self._on_fetch_finished)
        self.fetch_thread.start()
    
    def _on_fetch_finished(self, result: Optional[MusicBrainzResult]):
        """Handle completion of MusicBrainz fetch."""
        self.progress_bar.setVisible(False)
        
        if not result:
            QMessageBox.information(
                self,
                "No Results",
                "No matching track found on MusicBrainz.\n\n"
                "Try editing the metadata manually to improve matching."
            )
            self.reject()
            return
        
        self.fetched_result = result
        
        # Display fetched metadata
        self.fetched_title.setText(result.title or "(not available)")
        self.fetched_artist.setText(result.artist or "(not available)")
        self.fetched_album.setText(result.album or "(not available)")
        
        # Auto-check fields that are missing in current metadata
        if not self.current_metadata.get("title"):
            self.apply_title.setChecked(True)
        if not self.current_metadata.get("artist"):
            self.apply_artist.setChecked(True)
        if not self.current_metadata.get("album"):
            self.apply_album.setChecked(True)
        
        # Fetch cover art URL
        if result.release_mbid:
            try:
                self.cover_art_url = self.musicbrainz_service.get_cover_art(result.release_mbid)
                if self.cover_art_url:
                    self.download_artwork_button.setEnabled(True)
                    self.cover_preview.setText("Artwork available (click Download)")
                else:
                    self.cover_preview.setText("No artwork found")
            except Exception as e:
                logger.debug(f"Error fetching cover art URL: {e}")
    
    def _download_artwork(self):
        """Download and preview cover art."""
        if not self.cover_art_url:
            return
        
        try:
            # Download to cache directory
            cache_dir = Path.home() / ".local_audio_manager" / "artwork"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename from release MBID or track path
            if self.fetched_result and self.fetched_result.release_mbid:
                filename = f"{self.fetched_result.release_mbid}.jpg"
            else:
                filename = f"{self.file_path.stem}.jpg"
            
            artwork_path = cache_dir / filename
            
            if self.musicbrainz_service.download_cover_art(self.cover_art_url, artwork_path):
                # Display preview
                pixmap = QPixmap(str(artwork_path))
                scaled_pixmap = pixmap.scaled(
                    self.cover_preview.width(),
                    250,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.cover_preview.setPixmap(scaled_pixmap)
                self.artwork_path = artwork_path
                
                QMessageBox.information(
                    self,
                    "Artwork Downloaded",
                    f"Artwork saved to:\n{artwork_path}"
                )
            else:
                QMessageBox.warning(self, "Error", "Failed to download artwork.")
        
        except Exception as e:
            logger.error(f"Error downloading artwork: {e}")
            QMessageBox.warning(self, "Error", f"Failed to download artwork: {e}")
    
    def _apply_metadata(self):
        """Apply selected metadata fields."""
        if not self.fetched_result:
            return
        
        # Check if anything is selected
        if not any([
            self.apply_title.isChecked(),
            self.apply_artist.isChecked(),
            self.apply_album.isChecked()
        ]):
            QMessageBox.warning(self, "No Selection", "Please select at least one field to apply.")
            return
        
        self.applied_fields = {
            "title": self.fetched_result.title if self.apply_title.isChecked() else None,
            "artist": self.fetched_result.artist if self.apply_artist.isChecked() else None,
            "album": self.fetched_result.album if self.apply_album.isChecked() else None,
        }
        
        self.accept()

