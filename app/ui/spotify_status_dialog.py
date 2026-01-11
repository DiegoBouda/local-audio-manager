from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QGroupBox,
    QFormLayout,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SpotifyStatusDialog(QDialog):
    """Dialog showing why a track isn't visible in Spotify."""
    
    def __init__(self, track_path: str, status_info: dict, suggestions: list, parent=None):
        super().__init__(parent)
        self.track_path = track_path
        self.status_info = status_info
        self.suggestions = suggestions
        
        self.setWindowTitle("Spotify Status - Why isn't this track in Spotify?")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.resize(800, 650)
        
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Track info header
        header_group = QGroupBox("Track Information")
        header_layout = QVBoxLayout(header_group)
        header_layout.setSpacing(8)
        
        filename_label = QLabel(self.status_info["filename"])
        filename_label.setWordWrap(True)
        filename_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 5px;")
        
        path_text = QTextEdit()
        path_text.setPlainText(str(Path(self.track_path).parent))
        path_text.setReadOnly(True)
        path_text.setMaximumHeight(50)
        path_text.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd; padding: 5px; font-size: 11px; color: #000;")
        
        header_layout.addWidget(QLabel("File:"))
        header_layout.addWidget(filename_label)
        header_layout.addWidget(QLabel("Location:"))
        header_layout.addWidget(path_text)
        
        layout.addWidget(header_group)
        
        # Status summary
        status_summary = QGroupBox("Status Summary")
        status_layout = QVBoxLayout(status_summary)
        status_layout.setSpacing(10)
        
        if self.status_info["is_spotify_ready"]:
            status_text = QLabel("✓ Ready for Spotify")
            status_text.setStyleSheet("color: #2e7d32; font-weight: bold; font-size: 15px; padding: 5px;")
        else:
            status_text = QLabel("✗ Not Ready for Spotify")
            status_text.setStyleSheet("color: #c62828; font-weight: bold; font-size: 15px; padding: 5px;")
        
        status_layout.addWidget(status_text)
        
        if self.status_info["issues"]:
            issues_text = QTextEdit()
            issues_text.setPlainText("Issues found:\n• " + "\n• ".join(self.status_info["issues"]))
            issues_text.setReadOnly(True)
            issues_text.setMaximumHeight(80)
            issues_text.setStyleSheet("background-color: #fff3e0; border: 1px solid #ffb74d; padding: 8px; font-size: 12px; color: #000;")
            status_layout.addWidget(issues_text)
        
        layout.addWidget(status_summary)
        
        # Detailed checks
        checks_group = QGroupBox("Detailed Checks")
        checks_layout = QVBoxLayout(checks_group)
        checks_layout.setSpacing(12)
        
        # File exists
        checks_layout.addWidget(self._create_check_widget(
            "File Exists",
            self.status_info["checks"]["file_exists"],
            self.status_info["details"].get("file_exists", "")
        ))
        
        # Supported format
        checks_layout.addWidget(self._create_check_widget(
            "Supported Format",
            self.status_info["checks"]["supported_format"],
            self.status_info["details"].get("supported_format", "")
        ))
        
        # In Spotify folder
        checks_layout.addWidget(self._create_check_widget(
            "In Spotify Folder",
            self.status_info["checks"]["in_spotify_folder"],
            self.status_info["details"].get("in_spotify_folder", "")
        ))
        
        # Permissions
        checks_layout.addWidget(self._create_check_widget(
            "Read Permissions",
            self.status_info["checks"]["has_read_permission"],
            self.status_info["details"].get("has_read_permission", "")
        ))
        
        # Metadata
        checks_layout.addWidget(self._create_check_widget(
            "Metadata Valid",
            self.status_info["checks"]["metadata_valid"],
            self.status_info["details"].get("metadata_valid", "")
        ))
        
        layout.addWidget(checks_group)
        
        # Metadata content (if available)
        if "metadata_content" in self.status_info["details"]:
            meta_group = QGroupBox("Metadata Content")
            meta_layout = QVBoxLayout(meta_group)
            meta_text = QTextEdit()
            meta_text.setPlainText(self.status_info["details"]["metadata_content"])
            meta_text.setReadOnly(True)
            meta_text.setMaximumHeight(100)
            meta_text.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd; padding: 8px; font-size: 12px; font-family: monospace; color: #000;")
            meta_layout.addWidget(meta_text)
            layout.addWidget(meta_group)
        
        # Suggestions
        suggestions_group = QGroupBox("Suggestions")
        suggestions_layout = QVBoxLayout(suggestions_group)
        
        suggestions_text = QTextEdit()
        suggestions_text.setPlainText("\n".join(self.suggestions))
        suggestions_text.setReadOnly(True)
        suggestions_text.setMaximumHeight(150)
        suggestions_text.setStyleSheet("background-color: #e3f2fd; border: 1px solid #90caf9; padding: 10px; font-size: 12px; line-height: 1.5; color: #000;")
        suggestions_layout.addWidget(suggestions_text)
        
        layout.addWidget(suggestions_group)
        
        layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)
    
    def _create_check_widget(self, label_text: str, passed: bool, details: str) -> QWidget:
        """Create a widget with check status and details."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Label with status
        status_label = QLabel()
        if passed:
            status_label.setText(f"✓ {label_text}")
            status_label.setStyleSheet("color: #2e7d32; font-weight: bold; font-size: 13px;")
        else:
            status_label.setText(f"✗ {label_text}")
            status_label.setStyleSheet("color: #c62828; font-weight: bold; font-size: 13px;")
        
        layout.addWidget(status_label)
        
        # Details text
        details_text = QTextEdit()
        details_text.setPlainText(details)
        details_text.setReadOnly(True)
        details_text.setMaximumHeight(60)
        
        if passed:
            details_text.setStyleSheet("background-color: #e8f5e9; border: 1px solid #81c784; padding: 6px; font-size: 11px; color: #000;")
        else:
            details_text.setStyleSheet("background-color: #ffebee; border: 1px solid #ef5350; padding: 6px; font-size: 11px; color: #000;")
        
        layout.addWidget(details_text)
        
        return widget

