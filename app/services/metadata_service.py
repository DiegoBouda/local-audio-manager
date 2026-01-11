import logging
from pathlib import Path
from typing import Optional, Dict, Any
from mutagen import File
from mutagen.id3 import ID3NoHeaderError
from mutagen.easyid3 import EasyID3

logger = logging.getLogger(__name__)


class MetadataService:
    """Service for editing audio file metadata."""
    
    def __init__(self):
        pass
    
    def get_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Get metadata from an audio file."""
        try:
            audio = File(str(file_path), easy=True)
            
            if not audio:
                return {}
            
            metadata = {
                "title": audio.get("title", [""])[0] if audio.get("title") else "",
                "artist": audio.get("artist", [""])[0] if audio.get("artist") else "",
                "album": audio.get("album", [""])[0] if audio.get("album") else "",
                "genre": audio.get("genre", [""])[0] if audio.get("genre") else "",
                "year": None,
                "artwork": None
            }
            
            # Extract year
            if "date" in audio:
                try:
                    date_str = str(audio.get("date", [""])[0])
                    metadata["year"] = int(date_str[:4]) if date_str[:4].isdigit() else None
                except (ValueError, IndexError):
                    pass
            
            # Extract artwork
            metadata["artwork"] = self._get_artwork(file_path)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to read metadata from {file_path}: {e}")
            return {}
    
    def _get_artwork(self, file_path: Path) -> Optional[bytes]:
        """Extract artwork from audio file."""
        try:
            audio = File(str(file_path), easy=False)
            if not audio or not hasattr(audio, 'tags') or not audio.tags:
                return None
            
            suffix = file_path.suffix.lower()
            
            if suffix == '.mp3':
                # MP3 uses APIC frames
                try:
                    from mutagen.id3 import ID3
                    id3 = ID3(str(file_path))
                    for key in id3.keys():
                        if key.startswith('APIC'):
                            return bytes(id3[key].data)
                except ID3NoHeaderError:
                    pass
            
            elif suffix in ['.m4a', '.mp4']:
                # MP4/M4A uses 'covr' tag
                if 'covr' in audio.tags:
                    return bytes(audio.tags['covr'][0])
            
            elif suffix == '.flac':
                # FLAC uses PICTURE block
                if hasattr(audio, 'pictures') and audio.pictures:
                    return bytes(audio.pictures[0].data)
        
        except Exception as e:
            logger.debug(f"Could not extract artwork: {e}")
        
        return None
    
    def set_metadata(self, file_path: Path, title=None, artist=None, album=None, 
                     genre=None, year=None, artwork_path=None) -> bool:
        """Set metadata for an audio file."""
        try:
            # Try EasyID3 first (works for MP3, OGG, FLAC)
            try:
                audio = EasyID3(str(file_path))
            except ID3NoHeaderError:
                # Create ID3 tags if they don't exist
                try:
                    from mutagen.id3 import ID3
                    id3 = ID3()
                    id3.save(str(file_path))
                    audio = EasyID3(str(file_path))
                except:
                    audio = None
            
            if audio is None:
                # Fallback to regular File object (for M4A, MP4)
                audio = File(str(file_path), easy=False)
                if audio.tags is None:
                    try:
                        audio.add_tags()
                    except:
                        pass
            
            if audio is None:
                logger.error(f"Cannot edit file: {file_path}")
                return False
            
            # Set tags using EasyID3 interface
            if isinstance(audio, EasyID3):
                if title is not None:
                    audio["title"] = title
                if artist is not None:
                    audio["artist"] = artist
                if album is not None:
                    audio["album"] = album
                if genre is not None:
                    audio["genre"] = genre
                if year is not None:
                    audio["date"] = str(year)
                
                audio.save()
            else:
                # For M4A/MP4, use different tag names
                if title is not None:
                    audio.tags["\xa9nam"] = [title]
                if artist is not None:
                    audio.tags["\xa9ART"] = [artist]
                if album is not None:
                    audio.tags["\xa9alb"] = [album]
                if genre is not None:
                    audio.tags["\xa9gen"] = [genre]
                if year is not None:
                    audio.tags["\xa9day"] = [str(year)]
                
                audio.save()
            
            # Set artwork if provided
            if artwork_path:
                self._set_artwork(file_path, artwork_path)
            
            logger.info(f"Updated metadata for: {file_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set metadata for {file_path}: {e}")
            return False
    
    def _set_artwork(self, file_path: Path, artwork_path: Path):
        """Set artwork/album cover for an audio file."""
        try:
            if not artwork_path.exists():
                return
            
            # Read image data
            with open(artwork_path, 'rb') as f:
                image_data = f.read()
            
            suffix = file_path.suffix.lower()
            
            if suffix == '.mp3':
                from mutagen.id3 import ID3, APIC, ID3NoHeaderError
                try:
                    id3 = ID3(str(file_path))
                except ID3NoHeaderError:
                    id3 = ID3()
                
                # Determine MIME type
                mime = 'image/jpeg'
                if artwork_path.suffix.lower() in ['.png']:
                    mime = 'image/png'
                
                # Remove existing APIC frames
                id3.delall('APIC')
                
                id3.add(APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=image_data
                ))
                id3.save(str(file_path))
            
            elif suffix in ['.m4a', '.mp4']:
                audio = File(str(file_path), easy=False)
                if audio.tags is None:
                    audio.add_tags()
                audio.tags['covr'] = [image_data]
                audio.save()
            
            elif suffix == '.flac':
                from mutagen.flac import FLAC, Picture
                audio = FLAC(str(file_path))
                
                # Remove existing pictures
                audio.clear_pictures()
                
                picture = Picture()
                picture.type = 3  # Cover (front)
                picture.mime = 'image/jpeg'
                if artwork_path.suffix.lower() == '.png':
                    picture.mime = 'image/png'
                picture.data = image_data
                audio.add_picture(picture)
                audio.save()
        
        except Exception as e:
            logger.error(f"Failed to set artwork: {e}")
    
    def remove_artwork(self, file_path: Path) -> bool:
        """Remove artwork from an audio file."""
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == '.mp3':
                from mutagen.id3 import ID3, ID3NoHeaderError
                try:
                    id3 = ID3(str(file_path))
                    id3.delall('APIC')
                    id3.save(str(file_path))
                except ID3NoHeaderError:
                    pass
            
            elif suffix in ['.m4a', '.mp4']:
                audio = File(str(file_path), easy=False)
                if audio.tags and 'covr' in audio.tags:
                    del audio.tags['covr']
                    audio.save()
            
            elif suffix == '.flac':
                audio = File(str(file_path), easy=False)
                if hasattr(audio, 'clear_pictures'):
                    audio.clear_pictures()
                    audio.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove artwork: {e}")
            return False
