# Local Audio Manager

A desktop application for managing local audio files with advanced metadata editing, duplicate detection, and Spotify integration capabilities.

## Features

### Core Functionality
- **Audio File Management**: Scan and index audio files from your local directories
- **Real-time Monitoring**: Automatic detection of new, modified, or deleted files using file system monitoring
- **Spotify Integration**: Verify which tracks are visible to Spotify and diagnose compatibility issues

### Metadata Management
- **In-app Tag Editing**: Edit track metadata (title, artist, album, genre, year, artwork) directly in the application
- **Batch Editing**: Apply metadata changes to multiple tracks simultaneously
- **MusicBrainz Integration**: Automatically fetch missing metadata from MusicBrainz database
  - Intelligent matching using artist, title, and duration
  - User approval workflow before applying fetched metadata
  - Album artwork download via Cover Art Archive
  - Rate limiting and caching for efficient API usage

### Duplicate Detection
- **Multiple Detection Methods**: Find duplicates by filename, file hash, or metadata comparison
- **Merge/Delete Options**: Clean up your library by merging or removing duplicate tracks
- **Batch Operations**: Handle multiple duplicate groups efficiently

### Spotify Compatibility Analysis
- **Compatibility Checker**: Analyze why tracks might not be visible in Spotify
- **Detailed Diagnostics**: Check for unsupported formats, path visibility, permissions, and metadata validity
- **Actionable Suggestions**: Get specific recommendations to fix compatibility issues

## Requirements

- Python 3.8+
- PySide6 (Qt 6)
- macOS, Linux, or Windows

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd local-audio-manager
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python main.py
```

### Basic Workflow

1. **Add Folders**: Use the folder selection to add directories containing your audio files
2. **Scan Library**: The application automatically scans and indexes your audio files
3. **Edit Metadata**: Right-click on tracks to edit metadata or fetch from MusicBrainz
4. **Check Spotify Status**: Use the context menu to analyze why tracks might not be visible in Spotify
5. **Find Duplicates**: Use the duplicate detection tool to clean up your library

### MusicBrainz Integration

To fetch missing metadata from MusicBrainz:

1. Open the metadata editor for a track
2. Click "Fetch from MusicBrainz"
3. Review the fetched metadata
4. Select which fields to apply
5. Optionally download album artwork
6. Apply changes

The application automatically handles:
- Rate limiting (1 request per second as per MusicBrainz guidelines)
- Caching of results to minimize API calls
- Duration-based matching for accurate results

## Project Structure

```
local-audio-manager/
├── app/
│   ├── services/          # Business logic services
│   │   ├── db_service.py           # Database operations
│   │   ├── index_service.py        # File indexing
│   │   ├── watch_service.py        # File system monitoring
│   │   ├── metadata_service.py     # Metadata editing
│   │   ├── musicbrainz_service.py  # MusicBrainz API integration
│   │   ├── duplicate_service.py    # Duplicate detection
│   │   └── spotify_status_service.py # Spotify compatibility
│   ├── ui/                # User interface components
│   │   ├── main_window.py
│   │   ├── metadata_dialog.py
│   │   ├── musicbrainz_fetch_dialog.py
│   │   ├── duplicate_dialog.py
│   │   └── spotify_status_dialog.py
│   ├── helpers/           # Utility functions
│   └── models/            # Data models
├── tests/                 # Test suite
├── main.py               # Application entry point
└── requirements.txt      # Python dependencies
```

## Testing

The project includes a comprehensive test suite:

```bash
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests.test_musicbrainz_service

# Run with pytest (if installed)
pytest tests/
```

Tests are organized by component and use mocking for external dependencies (API calls, file system operations). See `tests/README.md` for more details.

## Technical Details

### Architecture
- **Service-Oriented Design**: Business logic separated into focused service classes
- **Thread-Safe Database**: SQLite with proper locking for concurrent access
- **Background Processing**: File system monitoring and metadata fetching run in separate threads
- **Event-Driven UI**: Qt signals/slots for thread-safe UI updates

### Key Technologies
- **PySide6**: Modern Qt-based GUI framework
- **mutagen**: Audio metadata reading and writing
- **watchdog**: Real-time file system event monitoring
- **requests**: HTTP client for MusicBrainz API
- **SQLite**: Embedded database for track storage

### MusicBrainz Integration
- Respects rate limits (1 request/second)
- Implements caching to minimize API calls
- Uses duration matching for accurate track identification
- Follows MusicBrainz API best practices

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Write tests for new features
2. Follow the existing code style
3. Ensure all tests pass before submitting
4. Document new features and API changes

## License

[Add your license here]

## Acknowledgments

- MusicBrainz for providing the music metadata database
- Cover Art Archive for album artwork
- The Qt Project for the excellent GUI framework

