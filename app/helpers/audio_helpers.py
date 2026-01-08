from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac"}

def is_supported_audio(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS

def is_visible_to_spotify(track_path: Path, spotify_folder: Path) -> bool:
    return spotify_folder in track_path.parents