from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QListWidget,
    QToolBar,
    QFileDialog,
    QSplitter,
    QLineEdit,
    QWidget,
    QVBoxLayout
)
from PySide6.QtCore import Qt
from shutil import copy2
from pathlib import Path

from app.services.config_service import ConfigService
from app.services.db_service import DBService
from app.services.index_service import IndexService
from app.helpers.audio_helpers import (
    is_supported_audio,
    is_visible_to_spotify
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Services
        self.config = ConfigService()
        self.db_service = DBService()
        self.index_service = IndexService(self.db_service)

        # UI
        self._setup_window()
        self._setup_widgets()
        self._setup_toolbar()
        self._connect_signals()

        self.load_folders()
        self.load_tracks()

    # ---------- Setup ----------

    def _setup_window(self):
        self.setWindowTitle("Local Audio Manager")

    def _setup_widgets(self):
        self.folder_list = QListWidget()
        self.track_list = QListWidget()

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

    def _setup_toolbar(self):
        toolbar = QToolBar("Actions")
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.scan_button)
        toolbar.addWidget(self.set_spotify_button)
        self.addToolBar(toolbar)

    def _connect_signals(self):
        self.add_button.clicked.connect(self.add_folder)
        self.scan_button.clicked.connect(self.scan_library)
        self.search_bar.textChanged.connect(self.apply_search_filter)
        self.set_spotify_button.clicked.connect(self.set_spotify_folder)

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

    def set_spotify_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Spotify-visible Folder")
        if folder:
            self.config.set_spotify_folder(folder)
            self.load_tracks()

    # ---------- Track Logic ----------

    def scan_library(self):
        for folder in self.config.get_music_folders():
            self.index_service.scan_folder(folder)
        self.load_tracks()

    def load_tracks(self):
        self.all_tracks = self.db_service.get_all_tracks()
        self.refresh_track_list(self.all_tracks)

    def refresh_track_list(self, tracks):
        self.track_list.clear()
        spotify_folder = (
            Path(self.config.get_spotify_folder())
            if self.config.get_spotify_folder()
            else None
        )

        for track in tracks:
            self.track_list.addItem(
                self.format_track_display(track, spotify_folder)
            )

    def format_track_display(self, track, spotify_folder):
        path = Path(track[1])

        if not is_supported_audio(path):
            status = "[✖ Incompatible]"
        elif spotify_folder and not is_visible_to_spotify(path, spotify_folder):
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

    # ---------- Spotify Prep ----------

    def prepare_for_spotify(self):
        spotify_folder = self.config.get_spotify_folder()
        if not spotify_folder:
            return

        spotify_folder = Path(spotify_folder)

        for track in self.db_service.get_all_tracks():
            path = Path(track[1])

            if not is_supported_audio(path):
                continue

            destination = spotify_folder / path.name
            if not destination.exists():
                copy2(path, destination)

        self.load_tracks()