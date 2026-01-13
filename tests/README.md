# Tests

This directory contains tests for the Local Audio Manager application.

## Structure

Tests are organized by component:

- `test_musicbrainz_service.py` - Tests for MusicBrainz service
  - API interaction (mocked)
  - Caching behavior
  - Data extraction and matching
  - Cover art functionality
  - Error handling

- `test_musicbrainz_fetch_dialog.py` - Tests for MusicBrainz fetch dialog logic
  - Metadata checking logic (no Qt widgets)
  - Edge cases and validation

## Running Tests

### Using pytest (recommended)

```bash
# Run all tests
pytest tests/

# Run only non-Qt tests (faster, no segfaults)
pytest tests/test_musicbrainz_service.py tests/test_musicbrainz_fetch_dialog.py

# Run Qt widget tests (requires pytest-qt)
pytest tests/test_musicbrainz_fetch_dialog_pytest.py

# Run specific test file
pytest tests/test_musicbrainz_service.py

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Using unittest

```bash
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests.test_musicbrainz_service

# Run specific test class
python -m unittest tests.test_musicbrainz_service.TestMusicBrainzServiceAPI
```

## Important Notes

### Qt Widget Testing

**Qt widgets are NOT tested in this suite** because:
- Creating Qt widgets requires proper QApplication setup
- Widget tests often cause segmentation faults in CI/unittest environments
- UI testing is better done manually or with dedicated UI testing tools

Instead, we test:
- **Business logic**: Metadata checking, validation, edge cases
- **Service layer**: API calls, caching, data processing
- **Data structures**: Result objects, data transformations

For UI testing:
- Use the application manually
- Consider dedicated UI testing frameworks if needed
- Focus automated tests on business logic and services

## Test Organization

Tests follow these principles:

1. **Separation of Concerns**: Each test class focuses on a specific aspect
   - API interaction
   - Caching
   - Data matching
   - Error handling

2. **Isolation**: Tests don't depend on each other
   - Each test sets up its own fixtures
   - Tests clean up after themselves

3. **Mocking**: External dependencies are mocked
   - HTTP requests to MusicBrainz API
   - File system operations (where appropriate)
   - UI components (for service tests)

4. **Clear Naming**: Test names describe what they test
   - `test_search_track_success` - Tests successful search
   - `test_cache_expiration` - Tests cache expiration logic

## Adding New Tests

When adding new functionality:

1. Create a new test class for the new component
2. Group related tests together
3. Use descriptive test names
4. Mock external dependencies
5. Clean up resources in `tearDown` or use fixtures

## Coverage Goals

- Aim for >80% code coverage
- Focus on critical paths and error handling
- Test edge cases and boundary conditions

