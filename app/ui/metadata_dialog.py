from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QSpinBox,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from pathlib import Path
import logging

from app.services.metadata_service import MetadataService
from app.services.db_service import DBService
from app.services.index_service import IndexService
from app.services.musicbrainz_service import MusicBrainzService
from app.ui.musicbrainz_fetch_dialog import MusicBrainzFetchDialog

logger = logging.getLogger(__name__)


class MetadataDialog(QDialog):
    """Dialog for editing audio file metadata."""
    
    def __init__(self, file_path: Path, metadata_service: MetadataService, 
                 db_service: DBService, index_service: IndexService,
                 musicbrainz_service: MusicBrainzService = None,
                 parent=None, batch_mode=False):
        super().__init__(parent)
        self.file_path = file_path
        self.metadata_service = metadata_service
        self.db_service = db_service
        self.index_service = index_service
        self.musicbrainz_service = musicbrainz_service
        self.batch_mode = batch_mode
        self.artwork_path = None
        
        self.setWindowTitle(f"Edit Metadata - {file_path.name}")
        self.setMinimumWidth(500)
        
        self._setup_ui()
        self._load_metadata()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Fetch from MusicBrainz button (if service available)
        if self.musicbrainz_service:
            fetch_button_layout = QHBoxLayout()
            self.fetch_mb_button = QPushButton("Fetch from MusicBrainz")
            self.fetch_mb_button.clicked.connect(self._fetch_from_musicbrainz)
            fetch_button_layout.addWidget(self.fetch_mb_button)
            fetch_button_layout.addStretch()
            layout.addLayout(fetch_button_layout)
        
        # Form fields
        form_group = QGroupBox("Metadata")
        form_layout = QFormLayout(form_group)
        
        self.title_edit = QLineEdit()
        self.artist_edit = QLineEdit()
        self.album_edit = QLineEdit()
        self.genre_edit = QLineEdit()
        self.year_spin = QSpinBox()
        self.year_spin.setMinimum(0)
        self.year_spin.setMaximum(9999)
        self.year_spin.setSpecialValueText("")
        
        form_layout.addRow("Title:", self.title_edit)
        form_layout.addRow("Artist:", self.artist_edit)
        form_layout.addRow("Album:", self.album_edit)
        form_layout.addRow("Genre:", self.genre_edit)
        form_layout.addRow("Year:", self.year_spin)
        
        layout.addWidget(form_group)
        
        # Artwork section
        artwork_group = QGroupBox("Album Artwork")
        artwork_layout = QVBoxLayout(artwork_group)
        
        artwork_buttons = QHBoxLayout()
        self.load_artwork_button = QPushButton("Load Image...")
        self.remove_artwork_button = QPushButton("Remove Artwork")
        self.artwork_preview = QLabel()
        self.artwork_preview.setMinimumHeight(150)
        self.artwork_preview.setMaximumHeight(300)
        self.artwork_preview.setAlignment(Qt.AlignCenter)
        self.artwork_preview.setText("No artwork")
        self.artwork_preview.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        
        artwork_buttons.addWidget(self.load_artwork_button)
        artwork_buttons.addWidget(self.remove_artwork_button)
        artwork_buttons.addStretch()
        
        artwork_layout.addLayout(artwork_buttons)
        artwork_layout.addWidget(self.artwork_preview)
        
        layout.addWidget(artwork_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._save_metadata)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
        # Connect signals
        self.load_artwork_button.clicked.connect(self._load_artwork)
        self.remove_artwork_button.clicked.connect(self._remove_artwork)
    
    def _load_metadata(self):
        """Load metadata from the file."""
        metadata = self.metadata_service.get_metadata(self.file_path)
        
        self.title_edit.setText(metadata.get("title", ""))
        self.artist_edit.setText(metadata.get("artist", ""))
        self.album_edit.setText(metadata.get("album", ""))
        self.genre_edit.setText(metadata.get("genre", ""))
        
        year = metadata.get("year")
        if year:
            self.year_spin.setValue(year)
        else:
            self.year_spin.setValue(0)
        
        # Get duration for MusicBrainz matching
        try:
            from mutagen import File
            audio = File(str(self.file_path), easy=True)
            self.duration = audio.info.length if audio and hasattr(audio, "info") else None
        except:
            self.duration = None
        
        # Load artwork
        artwork_data = metadata.get("artwork")
        if artwork_data:
            self._display_artwork(artwork_data)
    
    def _fetch_from_musicbrainz(self):
        """Fetch metadata from MusicBrainz."""
        if not self.musicbrainz_service:
            return
        
        # Get current metadata
        current_metadata = {
            "title": self.title_edit.text().strip(),
            "artist": self.artist_edit.text().strip(),
            "album": self.album_edit.text().strip(),
            "year": self.year_spin.value() if self.year_spin.value() > 0 else None,
            "duration": self.duration
        }
        
        # Open fetch dialog
        dialog = MusicBrainzFetchDialog(
            self.file_path,
            current_metadata,
            self.musicbrainz_service,
            parent=self
        )
        
        # If user canceled the initial prompt (clicked No), don't proceed
        if not dialog.should_fetch:
            return
        
        # Only show dialog if we're actually fetching
        if dialog.exec() and hasattr(dialog, 'applied_fields'):
            # Apply fetched metadata to form
            applied = dialog.applied_fields
            if applied.get("title"):
                self.title_edit.setText(applied["title"])
            if applied.get("artist"):
                self.artist_edit.setText(applied["artist"])
            if applied.get("album"):
                self.album_edit.setText(applied["album"])
            if applied.get("year"):
                self.year_spin.setValue(applied["year"])
            
            # Set artwork path if downloaded
            if hasattr(dialog, 'artwork_path') and dialog.artwork_path:
                self.artwork_path = dialog.artwork_path
                self._display_artwork_from_file(dialog.artwork_path)
    
    def _load_artwork(self):
        """Load artwork from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Artwork Image",
            "",
            "Image Files (*.png *.jpg *.jpeg)"
        )
        
        if file_path:
            self.artwork_path = Path(file_path)
            self._display_artwork_from_file(self.artwork_path)
    
    def _display_artwork(self, artwork_data: bytes):
        """Display artwork from bytes."""
        try:
            image = QImage.fromData(artwork_data)
            pixmap = QPixmap.fromImage(image)
            scaled_pixmap = pixmap.scaled(
                self.artwork_preview.width(),
                300,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.artwork_preview.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"Failed to display artwork: {e}")
            self.artwork_preview.setText("Error loading artwork")
    
    def _display_artwork_from_file(self, file_path: Path):
        """Display artwork from a file."""
        try:
            pixmap = QPixmap(str(file_path))
            scaled_pixmap = pixmap.scaled(
                self.artwork_preview.width(),
                300,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.artwork_preview.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"Failed to display artwork: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load image: {e}")
    
    def _remove_artwork(self):
        """Remove artwork from preview."""
        self.artwork_path = Path("")  # Mark for removal
        self.artwork_preview.clear()
        self.artwork_preview.setText("No artwork")
    
    def _save_metadata(self):
        """Save metadata to the file."""
        try:
            title = self.title_edit.text().strip() or None
            artist = self.artist_edit.text().strip() or None
            album = self.album_edit.text().strip() or None
            genre = self.genre_edit.text().strip() or None
            year = self.year_spin.value() if self.year_spin.value() > 0 else None
            
            # Save metadata to file
            success = self.metadata_service.set_metadata(
                self.file_path,
                title=title,
                artist=artist,
                album=album,
                genre=genre,
                year=year,
                artwork_path=self.artwork_path if self.artwork_path else None
            )
            
            if success:
                # Update database
                self.db_service.update_track(
                    str(self.file_path),
                    title=title,
                    artist=artist,
                    album=album,
                    genre=genre,
                    year=year
                )
                
                if not self.batch_mode:
                    QMessageBox.information(self, "Success", "Metadata updated successfully.")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to update metadata.")
        
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save metadata: {e}")


class BatchMetadataDialog(QDialog):
    """Dialog for batch editing metadata."""
    
    def __init__(self, file_paths: list[Path], metadata_service: MetadataService,
                 db_service: DBService, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.metadata_service = metadata_service
        self.db_service = db_service
        
        self.setWindowTitle(f"Batch Edit Metadata ({len(file_paths)} files)")
        self.setMinimumWidth(500)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(f"Editing {len(self.file_paths)} file(s).\n"
                           "Only checked fields will be applied to all files.")
        layout.addWidget(info_label)
        
        # Form fields with checkboxes
        form_group = QGroupBox("Metadata")
        form_layout = QFormLayout(form_group)
        
        self.title_check = QCheckBox()
        self.title_edit = QLineEdit()
        title_layout = QHBoxLayout()
        title_layout.addWidget(self.title_check)
        title_layout.addWidget(self.title_edit)
        form_layout.addRow("Title:", title_layout)
        
        self.artist_check = QCheckBox()
        self.artist_edit = QLineEdit()
        artist_layout = QHBoxLayout()
        artist_layout.addWidget(self.artist_check)
        artist_layout.addWidget(self.artist_edit)
        form_layout.addRow("Artist:", artist_layout)
        
        self.album_check = QCheckBox()
        self.album_edit = QLineEdit()
        album_layout = QHBoxLayout()
        album_layout.addWidget(self.album_check)
        album_layout.addWidget(self.album_edit)
        form_layout.addRow("Album:", album_layout)
        
        self.genre_check = QCheckBox()
        self.genre_edit = QLineEdit()
        genre_layout = QHBoxLayout()
        genre_layout.addWidget(self.genre_check)
        genre_layout.addWidget(self.genre_edit)
        form_layout.addRow("Genre:", genre_layout)
        
        self.year_check = QCheckBox()
        self.year_spin = QSpinBox()
        self.year_spin.setMinimum(0)
        self.year_spin.setMaximum(9999)
        self.year_spin.setSpecialValueText("")
        year_layout = QHBoxLayout()
        year_layout.addWidget(self.year_check)
        year_layout.addWidget(self.year_spin)
        form_layout.addRow("Year:", year_layout)
        
        layout.addWidget(form_group)
        
        # Artwork section
        artwork_group = QGroupBox("Album Artwork")
        artwork_layout = QVBoxLayout(artwork_group)
        
        self.artwork_check = QCheckBox("Apply artwork to all files")
        self.load_artwork_button = QPushButton("Load Image...")
        self.artwork_preview = QLabel()
        self.artwork_preview.setMinimumHeight(150)
        self.artwork_preview.setMaximumHeight(300)
        self.artwork_preview.setAlignment(Qt.AlignCenter)
        self.artwork_preview.setText("No artwork")
        self.artwork_preview.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        
        artwork_buttons = QHBoxLayout()
        artwork_buttons.addWidget(self.artwork_check)
        artwork_buttons.addWidget(self.load_artwork_button)
        artwork_buttons.addStretch()
        
        artwork_layout.addLayout(artwork_buttons)
        artwork_layout.addWidget(self.artwork_preview)
        
        layout.addWidget(artwork_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._save_metadata)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
        # Connect signals
        self.load_artwork_button.clicked.connect(self._load_artwork)
    
    def _load_artwork(self):
        """Load artwork from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Artwork Image",
            "",
            "Image Files (*.png *.jpg *.jpeg)"
        )
        
        if file_path:
            self.artwork_path = Path(file_path)
            self._display_artwork_from_file(self.artwork_path)
    
    def _display_artwork_from_file(self, file_path: Path):
        """Display artwork from a file."""
        try:
            pixmap = QPixmap(str(file_path))
            scaled_pixmap = pixmap.scaled(
                self.artwork_preview.width(),
                300,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.artwork_preview.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"Failed to display artwork: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load image: {e}")
    
    def _save_metadata(self):
        """Save metadata to all files."""
        try:
            title = self.title_edit.text().strip() if self.title_check.isChecked() else None
            artist = self.artist_edit.text().strip() if self.artist_check.isChecked() else None
            album = self.album_edit.text().strip() if self.album_check.isChecked() else None
            genre = self.genre_edit.text().strip() if self.genre_check.isChecked() else None
            year = self.year_spin.value() if self.year_check.isChecked() and self.year_spin.value() > 0 else None
            artwork_path = self.artwork_path if (self.artwork_check.isChecked() and hasattr(self, 'artwork_path')) else None
            
            if not any([title, artist, album, genre, year, artwork_path]):
                QMessageBox.warning(self, "No Changes", "Please select at least one field to update.")
                return
            
            # Process each file
            success_count = 0
            for file_path in self.file_paths:
                try:
                    if self.metadata_service.set_metadata(
                        file_path,
                        title=title,
                        artist=artist,
                        album=album,
                        genre=genre,
                        year=year,
                        artwork_path=artwork_path
                    ):
                        # Update database
                        self.db_service.update_track(
                            str(file_path),
                            title=title,
                            artist=artist,
                            album=album,
                            genre=genre,
                            year=year
                        )
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to update {file_path}: {e}")
            
            QMessageBox.information(
                self,
                "Batch Edit Complete",
                f"Successfully updated {success_count} out of {len(self.file_paths)} file(s)."
            )
            self.accept()
        
        except Exception as e:
            logger.error(f"Error in batch edit: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save metadata: {e}")

