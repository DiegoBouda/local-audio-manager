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
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QMenu,
    QInputDialog,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QTabWidget
)
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from shutil import copy2
from pathlib import Path
import logging

from app.services.config_service import ConfigService
from app.services.db_service import DBService
from app.services.index_service import IndexService
from app.services.watch_service import WatchService
from app.services.playlist_service import PlaylistService
from app.services.m3u_service import M3UService
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
        self.playlist_service = PlaylistService(self.db_service)
        self.m3u_service = M3UService(self.playlist_service)
        
        # Current playlist selection
        self.current_playlist_id = None

        # UI
        self._setup_window()
        self._setup_widgets()
        self._setup_toolbar()
        self._connect_signals()

        self.load_folders()
        self.load_tracks()
        self.load_playlists()
        
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
        # Left panel: Folders and Playlists
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Folders section
        folder_group = QGroupBox("Folders")
        folder_group_layout = QVBoxLayout(folder_group)
        self.folder_list = QListWidget()
        folder_group_layout.addWidget(self.folder_list)
        left_layout.addWidget(folder_group)
        
        # Playlists section
        playlist_group = QGroupBox("Playlists")
        playlist_group_layout = QVBoxLayout(playlist_group)
        
        playlist_buttons = QHBoxLayout()
        self.new_playlist_button = QPushButton("New")
        self.delete_playlist_button = QPushButton("Delete")
        self.rename_playlist_button = QPushButton("Rename")
        self.export_playlist_button = QPushButton("Export M3U")
        playlist_buttons.addWidget(self.new_playlist_button)
        playlist_buttons.addWidget(self.delete_playlist_button)
        playlist_buttons.addWidget(self.rename_playlist_button)
        playlist_buttons.addWidget(self.export_playlist_button)
        playlist_group_layout.addLayout(playlist_buttons)
        
        self.playlist_list = QListWidget()
        self.playlist_list.setContextMenuPolicy(Qt.CustomContextMenu)
        playlist_group_layout.addWidget(self.playlist_list)
        left_layout.addWidget(playlist_group)
        
        # Center panel: Tracks
        track_panel = QWidget()
        track_layout = QVBoxLayout(track_panel)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search tracks...")
        
        self.track_list = QListWidget()
        self.track_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.track_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.track_list.setDragEnabled(True)  # Enable dragging tracks to playlists
        
        track_layout.addWidget(QLabel("Library Tracks"))
        track_layout.addWidget(self.search_bar)
        track_layout.addWidget(self.track_list)
        
        # Right panel: Playlist Tracks
        playlist_track_panel = QWidget()
        playlist_track_layout = QVBoxLayout(playlist_track_panel)
        
        playlist_track_layout.addWidget(QLabel("Playlist Tracks"))
        
        self.playlist_track_list = QListWidget()
        self.playlist_track_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_track_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.playlist_track_list.setDragDropMode(QListWidget.InternalMove)  # Enable drag-and-drop reordering
        self.playlist_track_list.setDefaultDropAction(Qt.MoveAction)
        
        playlist_track_buttons = QHBoxLayout()
        self.remove_from_playlist_button = QPushButton("Remove")
        playlist_track_buttons.addWidget(self.remove_from_playlist_button)
        playlist_track_layout.addLayout(playlist_track_buttons)
        playlist_track_layout.addWidget(self.playlist_track_list)
        
        # Main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(track_panel)
        main_splitter.addWidget(playlist_track_panel)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setStretchFactor(2, 1)

        self.setCentralWidget(main_splitter)

        self.add_button = QPushButton("Add Music Folder")
        self.scan_button = QPushButton("Scan Library")
        self.set_spotify_button = QPushButton("Set Spotify Folder")
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setStyleSheet("background-color: #d32f2f; color: white;")
        self.import_m3u_button = QPushButton("Import M3U")
        
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
        toolbar.addWidget(self.import_m3u_button)
        toolbar.addSeparator()
        toolbar.addWidget(self.status_label)
        self.addToolBar(toolbar)

    def _connect_signals(self):
        self.add_button.clicked.connect(self.add_folder)
        self.scan_button.clicked.connect(self.scan_library)
        self.search_bar.textChanged.connect(self.apply_search_filter)
        self.set_spotify_button.clicked.connect(self.set_spotify_folder)
        self.delete_button.clicked.connect(self.delete_selected_tracks)
        self.import_m3u_button.clicked.connect(self.import_m3u_playlist)
        
        # Playlist signals
        self.new_playlist_button.clicked.connect(self.create_playlist)
        self.delete_playlist_button.clicked.connect(self.delete_playlist)
        self.rename_playlist_button.clicked.connect(self.rename_playlist)
        self.export_playlist_button.clicked.connect(self.export_playlist_m3u)
        self.playlist_list.itemSelectionChanged.connect(self.on_playlist_selected)
        self.playlist_list.customContextMenuRequested.connect(self._show_playlist_context_menu)
        
        # Playlist tracks signals
        self.remove_from_playlist_button.clicked.connect(self.remove_tracks_from_playlist)
        self.playlist_track_list.customContextMenuRequested.connect(self._show_playlist_track_context_menu)
        # Connect to rowsMoved signal to detect drag-and-drop reordering
        self.playlist_track_list.model().rowsMoved.connect(lambda: self.on_playlist_track_reordered(None))
        
        # Context menu for track list
        self.track_list.customContextMenuRequested.connect(self._show_track_context_menu)
        
        # Drag and drop reordering - connect to signal from model
        # We'll handle reordering in load_playlist_tracks after items are moved
        
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
        
        # Add "Add to Playlist" submenu if tracks are selected
        selected_items = self.track_list.selectedItems()
        if selected_items and self.playlist_list.count() > 0:
            menu.addSeparator()
            add_to_playlist_menu = menu.addMenu("Add to Playlist")
            for i in range(self.playlist_list.count()):
                playlist_item = self.playlist_list.item(i)
                playlist_name = playlist_item.text()
                playlist_action = add_to_playlist_menu.addAction(playlist_name)
                playlist_action.setData(playlist_item.data(Qt.UserRole))
                playlist_action.triggered.connect(
                    lambda checked, pid=playlist_item.data(Qt.UserRole): self._add_selected_tracks_to_playlist(pid)
                )
        
        menu.exec(self.track_list.mapToGlobal(position))
    
    def _add_selected_tracks_to_playlist(self, playlist_id: int):
        """Add selected tracks from track list to a playlist."""
        selected_items = self.track_list.selectedItems()
        if not selected_items:
            return
        
        track_paths = [item.data(Qt.UserRole) for item in selected_items if item.data(Qt.UserRole)]
        
        added_count = 0
        for track_path in track_paths:
            track_id = self.playlist_service.get_track_id_by_path(track_path)
            if track_id:
                self.playlist_service.add_track_to_playlist(playlist_id, track_id)
                added_count += 1
        
        # If this is the current playlist, reload it
        if self.current_playlist_id == playlist_id:
            self.load_playlist_tracks()
        
        if added_count > 0:
            playlist_name = None
            for i in range(self.playlist_list.count()):
                item = self.playlist_list.item(i)
                if item.data(Qt.UserRole) == playlist_id:
                    playlist_name = item.text()
                    break
            
            QMessageBox.information(
                self,
                "Success",
                f"Added {added_count} track(s) to playlist '{playlist_name}'."
            )

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

    # ---------- Playlist Management ----------
    
    def load_playlists(self):
        """Load all playlists into the playlist list."""
        self.playlist_list.clear()
        playlists = self.playlist_service.get_all_playlists()
        for playlist_id, playlist_name in playlists:
            item = QListWidgetItem(playlist_name)
            item.setData(Qt.UserRole, playlist_id)
            self.playlist_list.addItem(item)
    
    def create_playlist(self):
        """Create a new playlist."""
        name, ok = QInputDialog.getText(
            self,
            "New Playlist",
            "Enter playlist name:"
        )
        if ok and name.strip():
            playlist_id = self.playlist_service.create_playlist(name.strip())
            if playlist_id:
                self.load_playlists()
                QMessageBox.information(self, "Success", f"Playlist '{name}' created successfully.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to create playlist. Name may already exist.")
    
    def delete_playlist(self):
        """Delete the selected playlist."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a playlist to delete.")
            return
        
        playlist_id = selected_items[0].data(Qt.UserRole)
        playlist_name = selected_items[0].text()
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the playlist '{playlist_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.playlist_service.delete_playlist(playlist_id)
            self.load_playlists()
            self.current_playlist_id = None
            self.playlist_track_list.clear()
    
    def rename_playlist(self):
        """Rename the selected playlist."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a playlist to rename.")
            return
        
        playlist_id = selected_items[0].data(Qt.UserRole)
        old_name = selected_items[0].text()
        
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Playlist",
            "Enter new playlist name:",
            text=old_name
        )
        if ok and new_name.strip():
            if self.playlist_service.rename_playlist(playlist_id, new_name.strip()):
                self.load_playlists()
                QMessageBox.information(self, "Success", "Playlist renamed successfully.")
            else:
                QMessageBox.warning(self, "Error", "Failed to rename playlist. Name may already exist.")
    
    def on_playlist_selected(self):
        """Handle playlist selection - load its tracks."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            self.current_playlist_id = None
            self.playlist_track_list.clear()
            return
        
        self.current_playlist_id = selected_items[0].data(Qt.UserRole)
        self.load_playlist_tracks()
    
    def load_playlist_tracks(self):
        """Load tracks for the currently selected playlist."""
        self.playlist_track_list.clear()
        if not self.current_playlist_id:
            return
        
        tracks = self.playlist_service.get_playlist_tracks(self.current_playlist_id)
        for track in tracks:
            track_id, path, title, artist, album, duration = track
            item_text = self.format_playlist_track_display(track)
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (track_id, path))
            self.playlist_track_list.addItem(item)
    
    def format_playlist_track_display(self, track):
        """Format track for display in playlist."""
        track_id, path, title, artist, album, duration = track
        artist = artist or "Unknown Artist"
        title = title or "Unknown Title"
        return f"{artist} - {title}"
    
    def _show_playlist_context_menu(self, position):
        """Show context menu for playlist list."""
        if self.playlist_list.itemAt(position) is None:
            return
        
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        export_action = menu.addAction("Export M3U")
        
        rename_action.triggered.connect(self.rename_playlist)
        delete_action.triggered.connect(self.delete_playlist)
        export_action.triggered.connect(self.export_playlist_m3u)
        
        menu.exec(self.playlist_list.mapToGlobal(position))
    
    def add_tracks_to_playlist(self, track_paths: list):
        """Add tracks to the current playlist."""
        if not self.current_playlist_id:
            QMessageBox.information(self, "No Playlist", "Please select a playlist first.")
            return
        
        added_count = 0
        for track_path in track_paths:
            track_id = self.playlist_service.get_track_id_by_path(track_path)
            if track_id:
                self.playlist_service.add_track_to_playlist(self.current_playlist_id, track_id)
                added_count += 1
        
        self.load_playlist_tracks()
        if added_count > 0:
            QMessageBox.information(self, "Success", f"Added {added_count} track(s) to playlist.")
    
    def remove_tracks_from_playlist(self):
        """Remove selected tracks from the current playlist."""
        if not self.current_playlist_id:
            return
        
        selected_items = self.playlist_track_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select tracks to remove.")
            return
        
        count = len(selected_items)
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove {count} track(s) from playlist?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for item in selected_items:
                track_id, _ = item.data(Qt.UserRole)
                self.playlist_service.remove_track_from_playlist(self.current_playlist_id, track_id)
            
            self.load_playlist_tracks()
    
    def _show_playlist_track_context_menu(self, position):
        """Show context menu for playlist track list."""
        if self.playlist_track_list.itemAt(position) is None:
            return
        
        menu = QMenu(self)
        remove_action = menu.addAction("Remove from Playlist")
        remove_action.triggered.connect(self.remove_tracks_from_playlist)
        menu.exec(self.playlist_track_list.mapToGlobal(position))
    
    def on_playlist_track_reordered(self, item):
        """Handle when a track is reordered in the playlist (via drag-and-drop)."""
        if not self.current_playlist_id:
            return
        
        # Wait a moment for the move to complete, then update all positions
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._update_playlist_track_positions)
    
    def _update_playlist_track_positions(self):
        """Update all track positions in the database after reordering."""
        if not self.current_playlist_id:
            return
        
        # Collect all track IDs in their new order
        track_order = []
        for i in range(self.playlist_track_list.count()):
            item = self.playlist_track_list.item(i)
            if item:
                track_id, _ = item.data(Qt.UserRole)
                track_order.append((i, track_id))
        
        # Update positions starting from the end to avoid conflicts
        for new_position, track_id in reversed(track_order):
            self.playlist_service.reorder_track_in_playlist(
                self.current_playlist_id,
                track_id,
                new_position
            )
    
    def export_playlist_m3u(self):
        """Export the selected playlist to M3U format."""
        selected_items = self.playlist_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a playlist to export.")
            return
        
        playlist_id = selected_items[0].data(Qt.UserRole)
        playlist_name = selected_items[0].text()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Playlist",
            f"{playlist_name}.m3u",
            "M3U Playlist (*.m3u)"
        )
        
        if file_path:
            output_path = Path(file_path)
            if self.m3u_service.export_playlist_to_m3u(playlist_id, output_path, use_relative_paths=False):
                QMessageBox.information(self, "Success", f"Playlist exported to {file_path}")
            else:
                QMessageBox.warning(self, "Error", "Failed to export playlist.")
    
    def import_m3u_playlist(self):
        """Import a playlist from an M3U file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Playlist",
            "",
            "M3U Playlist (*.m3u)"
        )
        
        if file_path:
            m3u_path = Path(file_path)
            playlist_name = m3u_path.stem
            
            # Ask for playlist name
            name, ok = QInputDialog.getText(
                self,
                "Import Playlist",
                "Enter playlist name:",
                text=playlist_name
            )
            
            if ok and name.strip():
                if self.m3u_service.import_playlist_from_m3u(m3u_path, name.strip()):
                    self.load_playlists()
                    QMessageBox.information(self, "Success", f"Playlist imported successfully.")
                else:
                    QMessageBox.warning(self, "Error", "Failed to import playlist.")

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