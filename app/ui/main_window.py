from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QToolBar,
    QFileDialog,
    QSplitter,
    QLineEdit,
    QWidget,
    QVBoxLayout,
    QLabel,
    QMessageBox,
    QMenu
)
from PySide6.QtCore import Qt
from shutil import copy2
from pathlib import Path
import logging

from app.services.config_service import ConfigService
from app.services.db_service import DBService
from app.services.index_service import IndexService
from app.services.watch_service import WatchService
from app.helpers.audio_helpers import (
    is_supported_audio,
    is_visible_to_spotify
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Services
        self.config = ConfigService()
        self.db_service = DBService()
        self.index_service = IndexService(self.db_service)
        self.watch_service = WatchService(self.index_service, self.db_service)

        # UI
        self._setup_window()
        self._setup_widgets()
        self._setup_toolbar()
        self._connect_signals()

        self.load_folders()
        self.load_tracks()
        
        # Start watching configured folders
        self._start_file_watching()
    
    def closeEvent(self, event):
        """Handle application close - stop file watching."""
        self.watch_service.stop_watching()
        event.accept()

    # ---------- Setup ----------

    def _setup_window(self):
        self.setWindowTitle("Local Audio Manager")

    def _setup_widgets(self):
        self.folder_list = QListWidget()
        self.track_list = QListWidget()
        self.track_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.track_list.setSelectionMode(QListWidget.ExtendedSelection)  # Allow multiple selection

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search tracks...")

        track_panel = QWidget()
        track_layout = QVBoxLayout(track_panel)
        track_layout.addWidget(self.search_bar)
        track_layout.addWidget(self.track_list)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.folder_list)
        splitter.addWidget(track_panel)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        self.add_button = QPushButton("Add Music Folder")
        self.scan_button = QPushButton("Scan Library")
        self.set_spotify_button = QPushButton("Set Spotify Folder")
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setStyleSheet("background-color: #d32f2f; color: white;")
        
        # Status label for monitoring
        self.status_label = QLabel("Monitoring: Off")
        self.status_label.setStyleSheet("color: gray;")

    def _setup_toolbar(self):
        toolbar = QToolBar("Actions")
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.scan_button)
        toolbar.addWidget(self.set_spotify_button)
        toolbar.addSeparator()
        toolbar.addWidget(self.delete_button)
        toolbar.addSeparator()
        toolbar.addWidget(self.status_label)
        self.addToolBar(toolbar)

    def _connect_signals(self):
        self.add_button.clicked.connect(self.add_folder)
        self.scan_button.clicked.connect(self.scan_library)
        self.search_bar.textChanged.connect(self.apply_search_filter)
        self.set_spotify_button.clicked.connect(self.set_spotify_folder)
        self.delete_button.clicked.connect(self.delete_selected_tracks)
        
        # Context menu for track list
        self.track_list.customContextMenuRequested.connect(self._show_track_context_menu)
        
        # Connect watch service signal for automatic updates
        self.watch_service.library_updated.connect(self.load_tracks)

    # ---------- Folder Logic ----------

    def load_folders(self):
        self.folder_list.clear()
        for folder in self.config.get_music_folders():
            self.folder_list.addItem(folder)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder or not Path(folder).is_dir():
            return
        self.config.add_music_folder(folder)
        self.load_folders()
        # Add to watch service
        self.watch_service.add_folder(folder)
        self._update_status_label()

    def set_spotify_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Spotify-visible Folder")
        if folder:
            self.config.add_spotify_folder(folder)
            self.load_tracks()

    # ---------- Track Logic ----------

    def scan_library(self):
        """Perform a full scan of all music folders."""
        for folder in self.config.get_music_folders():
            self.index_service.scan_folder(folder)
        self.load_tracks()
    
    def _start_file_watching(self):
        """Start watching configured music folders for changes."""
        folders = self.config.get_music_folders()
        if folders:
            self.watch_service.start_watching(folders)
            self._update_status_label()
    
    def _update_status_label(self):
        """Update the status label to show monitoring state."""
        watched_count = len(self.watch_service.watched_paths)
        if self.watch_service.is_running and watched_count > 0:
            self.status_label.setText(f"Monitoring: {watched_count} folder(s)")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("Monitoring: Off")
            self.status_label.setStyleSheet("color: gray;")

    def load_tracks(self):
        self.all_tracks = self.db_service.get_all_tracks()
        self.refresh_track_list(self.all_tracks)

    def refresh_track_list(self, tracks):
        self.track_list.clear()
        spotify_folders = [
            Path(p) for p in self.config.get_spotify_folders()
        ]
        for track in tracks:
            item_text = self.format_track_display(track, spotify_folders)
            item = QListWidgetItem(item_text)
            # Store track data (path) as item data for deletion
            item.setData(Qt.UserRole, track[1])
            self.track_list.addItem(item)

    def format_track_display(self, track, spotify_folders):
        path = Path(track[1])
        if not is_supported_audio(path):
            status = "[✖ Incompatible]"
        elif spotify_folders and not is_visible_to_spotify(path, spotify_folders):
            status = "[⚠ Not Visible]"
        else:
            status = "[✔ Ready]"

        artist = track[3] or "Unknown Artist"
        title = track[2] or "Unknown Title"

        return f"{status} {artist} - {title}"

    def apply_search_filter(self):
        query = self.search_bar.text().lower()

        if not query:
            self.refresh_track_list(self.all_tracks)
            return

        filtered = []
        for track in self.all_tracks:
            if (
                query in (track[2] or "").lower()
                or query in (track[3] or "").lower()
                or query in (track[4] or "").lower()
            ):
                filtered.append(track)

        self.refresh_track_list(filtered)

    # ---------- Track Deletion ----------

    def _show_track_context_menu(self, position):
        """Show context menu when right-clicking on track list."""
        if self.track_list.itemAt(position) is None:
            return
        
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Selected Track(s)")
        delete_action.triggered.connect(self.delete_selected_tracks)
        menu.exec(self.track_list.mapToGlobal(position))

    def delete_selected_tracks(self):
        """Delete selected tracks from the database."""
        selected_items = self.track_list.selectedItems()
        
        if not selected_items:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select one or more tracks to delete."
            )
            return
        
        # Confirmation dialog
        count = len(selected_items)
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {count} track(s) from the library?\n\n"
            "This will remove them from the database but will NOT delete the actual files.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_count = 0
            for item in selected_items:
                track_path = item.data(Qt.UserRole)
                if track_path:
                    try:
                        self.db_service.delete_track(track_path)
                        deleted_count += 1
                    except Exception as e:
                        logging.error(f"Error deleting track {track_path}: {e}")
            
            # Refresh the track list
            self.load_tracks()
            
            QMessageBox.information(
                self,
                "Deletion Complete",
                f"Successfully deleted {deleted_count} track(s) from the library."
            )

    # ---------- Spotify Prep ----------

    def prepare_for_spotify(self):
        spotify_folders = [
            Path(p) for p in self.config.get_spotify_folders()
        ]
        if not spotify_folders:
            return

        for track in self.db_service.get_all_tracks():
            path = Path(track[1])

            if not is_supported_audio(path):
                continue

            for folder in spotify_folders:
                destination = folder / path.name
                if not destination.exists():
                    copy2(path, destination)

        self.load_tracks()