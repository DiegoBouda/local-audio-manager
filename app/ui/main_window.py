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
from pathlib import Path
from app.services.config_service import ConfigService
from app.services.db_service import DBService
from app.services.index_service import IndexService

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Services
        self.config = ConfigService()
        self.db_service = DBService()
        self.index_service = IndexService(self.db_service)

        # Setup UI
        self._setup_window()
        self._setup_widgets()
        self._setup_toolbar()
        self._connect_signals()

        # Load initial data
        self.load_folders()
        self.load_tracks()

    # ---------- Setup Helpers ----------

    def _setup_window(self):
        self.setWindowTitle("Local Audio Manager")

    def _setup_widgets(self):
        # Folder list (left)
        self.folder_list = QListWidget()

        # Track list (right)
        self.track_list = QListWidget()

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search tracks...")

        # Track panel layout
        track_panel = QWidget()
        track_layout = QVBoxLayout(track_panel)
        track_layout.addWidget(self.search_bar)
        track_layout.addWidget(self.track_list)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.folder_list)
        splitter.addWidget(track_panel)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        # Buttons
        self.add_button = QPushButton("Add Music Folder")
        self.scan_button = QPushButton("Scan Library")

    def _setup_toolbar(self):
        toolbar = QToolBar("Actions")
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.scan_button)
        self.addToolBar(toolbar)

    def _connect_signals(self):
        self.add_button.clicked.connect(self.add_folder)
        self.scan_button.clicked.connect(self.scan_library)
        self.search_bar.textChanged.connect(self._apply_search_filter)

    # ---------- Folder & Track Logic ----------

    def load_folders(self):
        self.folder_list.clear()
        for folder in self.config.get_music_folders():
            self.folder_list.addItem(folder)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder or not Path(folder).is_dir():
            return
        self.config.add_music_folder(folder)

    def scan_library(self):
        """Scan all folders for audio files"""
        if not self.config.get_music_folders():
            return
        for folder in self.config.get_music_folders():
            self.index_service.scan_folder(folder)
        self.load_tracks()

    def load_tracks(self):
        self.all_tracks = []

        self.track_list.clear()
        for track in self.db_service.get_all_tracks():
            self.all_tracks.append(track)

        self._apply_search_filter()

    def _apply_search_filter(self):
        query = self.search_bar.text().lower()
        self.track_list.clear()

        for track in self.all_tracks:
            # (id, path, title, artist, album, duration)
            title = (track[2] or "").lower()
            artist = (track[3] or "").lower()
            album = (track[4] or "").lower()

            if (
                query in title
                or query in artist
                or query in album
            ):
                display = f"{track[3] or 'Unknown Artist'} - {track[2] or 'Unknown Title'} ({track[4] or 'Unknown Album'})"
                self.track_list.addItem(display)