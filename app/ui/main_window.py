from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QListWidget, QToolBar, QFileDialog
)
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
        # Reuse folder_list for tracks temporarily
        self.folder_list = QListWidget()
        self.setCentralWidget(self.folder_list)

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

    # ---------- Folder & Track Logic ----------

    def load_folders(self):
        """Load folder list (for Phase 2)"""
        # Optional: could have separate widget for folders
        pass  # kept minimal

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder or not Path(folder).is_dir():
            return
        self.config.add_music_folder(folder)

    def scan_library(self):
        """Scan all folders for audio files"""
        for folder in self.config.get_music_folders():
            self.index_service.scan_folder(folder)
        self.load_tracks()

    def load_tracks(self):
        """Load all tracks from DB and display in UI"""
        self.folder_list.clear()
        for track in self.db_service.get_all_tracks():
            # track = (id, path, title, artist, album, duration)
            display = f"{track[3]} - {track[2]} ({track[4]})"
            self.folder_list.addItem(display)