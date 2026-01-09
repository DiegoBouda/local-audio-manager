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
                "spotify_folders": []
            })
            return

        # migration for old configs
        data = self._read()
        if "spotify_visible_folder" in data:
            old = data.pop("spotify_visible_folder")
            data["spotify_folders"] = [old] if old else []
            self._write(data)

    def _read(self):
        with open(self.config_file, "r") as f:
            return json.load(f)

    def _write(self, data):
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    # ---------- Music folders ----------

    def get_music_folders(self):
        return self._read().get("music_folders", [])

    def add_music_folder(self, folder_path: str):
        data = self._read()
        if folder_path not in data["music_folders"]:
            data["music_folders"].append(folder_path)
            self._write(data)

    # ---------- Spotify folders ----------

    def get_spotify_folders(self):
        return self._read().get("spotify_folders", [])

    def add_spotify_folder(self, folder_path: str):
        data = self._read()
        if folder_path not in data["spotify_folders"]:
            data["spotify_folders"].append(folder_path)
            self._write(data)