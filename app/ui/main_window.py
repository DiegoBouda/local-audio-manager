from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QFileDialog,
    QListWidget,
    QToolBar
)
from pathlib import Path
from app.services.config_service import ConfigService

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.config = ConfigService()

        self._setup_window()
        self._setup_widgets()
        self._setup_toolbar()
        self._connect_signals()
        self.load_folders()

    def _setup_window(self):
        self.setWindowTitle("Local Audio Manager")

    def _setup_widgets(self):
        self.folder_list = QListWidget()
        self.setCentralWidget(self.folder_list)

        self.add_button = QPushButton("Add Music Folder")

    def _setup_toolbar(self):
        toolbar = QToolBar("Folders")
        toolbar.addWidget(self.add_button)
        self.addToolBar(toolbar)

    def _connect_signals(self):
        self.add_button.clicked.connect(self.add_folder)

    def load_folders(self):
        self.folder_list.clear()
        for folder in self.config.get_music_folders():
            self.folder_list.addItem(folder)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")

        if not folder:
            return

        if not Path(folder).is_dir():
            return

        self.config.add_music_folder(folder)
        self.load_folders()