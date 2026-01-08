import json
from pathlib import Path

class ConfigService:
    def __init__(self):
        self.config_dir = Path.home() / ".local_audio_manager"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        self.config_dir.mkdir(exist_ok=True)
        if not self.config_file.exists():
            self._write({
                "music_folders": [],
                "spotify_visible_folder": ""
            })

    def _read(self):
        with open(self.config_file, "r") as f:
            return json.load(f)

    def _write(self, data):
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_music_folders(self):
        return self._read()["music_folders"]

    def add_music_folder(self, folder_path):
        data = self._read()
        if folder_path not in data["music_folders"]:
            data["music_folders"].append(folder_path)
            self._write(data)

    def set_spotify_folder(self, path: str):
        data = self._read()
        data["spotify_visible_folder"] = path
        self._write(data)

    def get_spotify_folder(self) -> str:
        return self._read().get("spotify_visible_folder", "")