from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac"}

def is_supported_audio(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS

def is_visible_to_spotify(track_path: Path, spotify_folders: list[Path]) -> bool:
    for folder in spotify_folders:
        try:
            track_path.resolve().relative_to(folder.resolve())
            return True
        except ValueError:
            continue
    return False