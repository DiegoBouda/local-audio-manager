from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QProgressBar,
    QTabWidget,
    QWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from pathlib import Path
import logging

from app.services.duplicate_service import DuplicateService

logger = logging.getLogger(__name__)


class DuplicateDetectionThread(QThread):
    """Thread for running duplicate detection without blocking UI."""
    finished = Signal(dict, str)  # Emits (duplicates_dict, method)
    progress = Signal(str)  # Emits progress message
    
    def __init__(self, duplicate_service: DuplicateService, method: str):
        super().__init__()
        self.duplicate_service = duplicate_service
        self.method = method
    
    def run(self):
        try:
            self.progress.emit(f"Scanning for duplicates by {self.method}...")
            
            if self.method == "filename":
                duplicates = self.duplicate_service.find_duplicates_by_filename()
            elif self.method == "hash":
                duplicates = self.duplicate_service.find_duplicates_by_hash()
            elif self.method == "metadata":
                duplicates = self.duplicate_service.find_duplicates_by_metadata()
            else:
                duplicates = {}
            
            self.finished.emit(duplicates, self.method)
        except Exception as e:
            logger.error(f"Error in duplicate detection: {e}")
            self.finished.emit({}, self.method)


class DuplicateDialog(QDialog):
    """Dialog for finding and managing duplicate tracks."""
    
    def __init__(self, duplicate_service: DuplicateService, parent=None):
        super().__init__(parent)
        self.duplicate_service = duplicate_service
        self.current_duplicates = {}
        self.current_method = None
        
        self.setWindowTitle("Find Duplicates")
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        self._setup_detection_methods()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Detection method selection
        method_group = QGroupBox("Detection Method")
        method_layout = QVBoxLayout(method_group)
        
        self.method_group = QButtonGroup(self)
        self.filename_radio = QRadioButton("By Filename (fast)")
        self.hash_radio = QRadioButton("By File Hash (accurate, slower)")
        self.metadata_radio = QRadioButton("By Metadata (title, artist, album, duration)")
        
        self.method_group.addButton(self.filename_radio, 0)
        self.method_group.addButton(self.hash_radio, 1)
        self.method_group.addButton(self.metadata_radio, 2)
        
        self.filename_radio.setChecked(True)
        
        method_layout.addWidget(self.filename_radio)
        method_layout.addWidget(self.hash_radio)
        method_layout.addWidget(self.metadata_radio)
        
        scan_layout = QHBoxLayout()
        self.scan_button = QPushButton("Scan for Duplicates")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        scan_layout.addWidget(self.scan_button)
        scan_layout.addWidget(self.progress_bar)
        
        method_layout.addLayout(scan_layout)
        layout.addWidget(method_group)
        
        # Duplicate groups display
        duplicates_group = QGroupBox("Duplicate Groups")
        duplicates_layout = QVBoxLayout(duplicates_group)
        
        self.groups_list = QListWidget()
        self.groups_list.itemSelectionChanged.connect(self.on_group_selected)
        duplicates_layout.addWidget(QLabel("Duplicate Groups:"))
        duplicates_layout.addWidget(self.groups_list)
        
        layout.addWidget(duplicates_group)
        
        # Tracks in selected group
        tracks_group = QGroupBox("Tracks in Selected Group")
        tracks_layout = QVBoxLayout(tracks_group)
        
        tracks_layout.addWidget(QLabel("Select tracks to keep/delete:"))
        
        self.tracks_list = QListWidget()
        self.tracks_list.setSelectionMode(QListWidget.MultiSelection)
        tracks_layout.addWidget(self.tracks_list)
        
        action_layout = QHBoxLayout()
        self.merge_button = QPushButton("Merge (Keep Selected, Remove Others)")
        self.delete_button = QPushButton("Delete Selected from Database")
        self.delete_files_button = QPushButton("Delete Selected Files")
        self.delete_files_button.setStyleSheet("background-color: #d32f2f; color: white;")
        
        self.merge_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.delete_files_button.setEnabled(False)
        
        action_layout.addWidget(self.merge_button)
        action_layout.addWidget(self.delete_button)
        action_layout.addWidget(self.delete_files_button)
        action_layout.addStretch()
        
        tracks_layout.addLayout(action_layout)
        layout.addWidget(tracks_group)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Connect signals
        self.scan_button.clicked.connect(self.scan_duplicates)
        self.merge_button.clicked.connect(self.merge_duplicates)
        self.delete_button.clicked.connect(self.delete_duplicates)
        self.delete_files_button.clicked.connect(self.delete_files)
    
    def _setup_detection_methods(self):
        """Initialize detection thread."""
        self.detection_thread = None
    
    def scan_duplicates(self):
        """Scan for duplicates based on selected method."""
        # Get selected method
        if self.filename_radio.isChecked():
            method = "filename"
        elif self.hash_radio.isChecked():
            method = "hash"
        else:
            method = "metadata"
        
        # Disable scan button and show progress
        self.scan_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Create and start detection thread
        self.detection_thread = DuplicateDetectionThread(self.duplicate_service, method)
        self.detection_thread.finished.connect(self.on_detection_finished)
        self.detection_thread.start()
    
    def on_detection_finished(self, duplicates: dict, method: str):
        """Handle completion of duplicate detection."""
        self.scan_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        self.current_duplicates = duplicates
        self.current_method = method
        
        # Populate groups list
        self.groups_list.clear()
        self.tracks_list.clear()
        
        if not duplicates:
            QMessageBox.information(self, "No Duplicates", "No duplicates found using this method.")
            return
        
        # Add groups to list
        for key, tracks in duplicates.items():
            # Create display text
            if method == "filename":
                display = f"{tracks[0][2] or 'Unknown'} - {len(tracks)} files"
            elif method == "hash":
                display = f"Hash: {key[:8]}... - {len(tracks)} files"
            else:  # metadata
                artist = tracks[0][3] or "Unknown"
                title = tracks[0][2] or "Unknown"
                display = f"{artist} - {title} ({len(tracks)} files)"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, key)
            self.groups_list.addItem(item)
        
        QMessageBox.information(
            self,
            "Scan Complete",
            f"Found {len(duplicates)} duplicate group(s) with {sum(len(tracks) for tracks in duplicates.values())} total tracks."
        )
    
    def on_group_selected(self):
        """Handle selection of a duplicate group."""
        selected_items = self.groups_list.selectedItems()
        if not selected_items:
            self.tracks_list.clear()
            self.merge_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.delete_files_button.setEnabled(False)
            return
        
        key = selected_items[0].data(Qt.UserRole)
        tracks = self.current_duplicates.get(key, [])
        
        # Populate tracks list
        self.tracks_list.clear()
        for track in tracks:
            track_id, path, title, artist, album, genre, year, duration = track
            file_path = Path(path)
            
            # Format display
            artist_display = artist or "Unknown Artist"
            title_display = title or "Unknown Title"
            filename = file_path.name
            size = self._format_file_size(file_path) if file_path.exists() else "Missing"
            
            display = f"{artist_display} - {title_display}\n{filename} ({size})"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, track)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.tracks_list.addItem(item)
        
        # Enable action buttons
        if len(tracks) > 0:
            self.merge_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            self.delete_files_button.setEnabled(True)
    
    def _format_file_size(self, file_path: Path) -> str:
        """Format file size in human-readable format."""
        try:
            size = file_path.stat().st_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except:
            return "Unknown size"
    
    def merge_duplicates(self):
        """Merge duplicates by keeping selected tracks and removing others."""
        selected_items = self.groups_list.selectedItems()
        if not selected_items:
            return
        
        key = selected_items[0].data(Qt.UserRole)
        all_tracks = self.current_duplicates.get(key, [])
        
        # Get checked tracks (to keep)
        checked_tracks = []
        for i in range(self.tracks_list.count()):
            item = self.tracks_list.item(i)
            if item.checkState() == Qt.Checked:
                checked_tracks.append(item.data(Qt.UserRole))
        
        if len(checked_tracks) == 0:
            QMessageBox.warning(self, "No Selection", "Please select at least one track to keep.")
            return
        
        if len(checked_tracks) == len(all_tracks):
            QMessageBox.warning(self, "Invalid Selection", "Cannot merge - all tracks are selected to keep.")
            return
        
        # Determine tracks to remove
        tracks_to_keep = checked_tracks[0]
        tracks_to_remove = [t for t in all_tracks if t not in checked_tracks]
        
        reply = QMessageBox.question(
            self,
            "Confirm Merge",
            f"Keep {len(checked_tracks)} track(s) and remove {len(tracks_to_remove)} duplicate(s) from database?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            removed_count = self.duplicate_service.merge_duplicates(tracks_to_keep, tracks_to_remove)
            QMessageBox.information(self, "Merge Complete", f"Removed {removed_count} duplicate(s) from database.")
            
            # Refresh the group
            self.scan_duplicates()
            # Signal parent to refresh track list
            self.accept()
    
    def delete_duplicates(self):
        """Delete selected duplicates from database only."""
        selected_items = self.groups_list.selectedItems()
        if not selected_items:
            return
        
        # Get checked tracks
        checked_tracks = []
        for i in range(self.tracks_list.count()):
            item = self.tracks_list.item(i)
            if item.checkState() == Qt.Checked:
                checked_tracks.append(item.data(Qt.UserRole))
        
        if not checked_tracks:
            QMessageBox.warning(self, "No Selection", "Please select tracks to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete {len(checked_tracks)} track(s) from database?\n\n"
            "Files will NOT be deleted from disk.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_count = self.duplicate_service.delete_duplicates(checked_tracks, delete_files=False)
            QMessageBox.information(self, "Deletion Complete", f"Deleted {deleted_count} track(s) from database.")
            
            # Refresh
            self.scan_duplicates()
            self.accept()
    
    def delete_files(self):
        """Delete selected duplicates from database AND filesystem."""
        selected_items = self.groups_list.selectedItems()
        if not selected_items:
            return
        
        # Get checked tracks
        checked_tracks = []
        for i in range(self.tracks_list.count()):
            item = self.tracks_list.item(i)
            if item.checkState() == Qt.Checked:
                checked_tracks.append(item.data(Qt.UserRole))
        
        if not checked_tracks:
            QMessageBox.warning(self, "No Selection", "Please select tracks to delete.")
            return
        
        reply = QMessageBox.warning(
            self,
            "Confirm File Deletion",
            f"Permanently delete {len(checked_tracks)} track(s) from database AND filesystem?\n\n"
            "This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_count = self.duplicate_service.delete_duplicates(checked_tracks, delete_files=True)
            QMessageBox.information(self, "Deletion Complete", f"Deleted {deleted_count} track(s).")
            
            # Refresh
            self.scan_duplicates()
            self.accept()

