# Rock Paper Scissors - Test Suite

Comprehensive test harness for the Rock Paper Scissors application.

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_helpers.py          # Test utility functions
├── test_game_service.py     # Test game service logic
├── test_api.py              # Test API endpoints
├── test_routes.py           # Test FastAPI page/game routes
└── test_integration.py      # End-to-end integration tests
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
# Using the test runner script
./run_tests.sh

# Or directly with pytest
pytest
```

### Run Specific Test Types

```bash
# Unit tests only
./run_tests.sh unit

# Integration tests only
./run_tests.sh integration

# With coverage report
./run_tests.sh coverage

# Fast mode (no coverage)
./run_tests.sh fast
```

### Run Specific Test Files

```bash
# Test helpers only
pytest tests/test_helpers.py

# Test game service only
pytest tests/test_game_service.py -v

# Test a specific test class
pytest tests/test_helpers.py::TestWinnerDetermination

# Test a specific test function
pytest tests/test_helpers.py::TestWinnerDetermination::test_rock_beats_scissors
```

### Run with Options

```bash
# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Run last failed tests
pytest --lf

# Run tests matching pattern
pytest -k "winner"
```

## Test Coverage

Generate detailed coverage report:

```bash
./run_tests.sh coverage
```

View the HTML coverage report:

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Test Categories

### Unit Tests (`test_helpers.py`, `test_game_service.py`)
- Test individual functions in isolation
- Mock the `Game`/`Round` model layer (SQLite via aiosqlite)
- Fast execution
- High coverage of edge cases

### API Tests (`test_api.py`)
- Test API endpoints
- Verify request/response formats
- Test authentication and authorization
- Error handling

### Route Tests (`test_routes.py`)
- Test FastAPI routes
- Verify page rendering
- Test session management (Starlette `SessionMiddleware`)
- Redirect logic

### Integration Tests (`test_integration.py`)
- End-to-end game flow
- Multiple components working together
- Slower but more realistic
- Catch integration issues

## Writing New Tests

### Example Test

```python
import pytest
from app.utils.helpers import determine_winner

class TestNewFeature:
    """Test new feature."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        result = determine_winner('rock', 'scissors')
        assert result == 'host'

    def test_edge_case(self):
        """Test edge case."""
        result = determine_winner('rock', 'rock')
        assert result == 'tie'

    @pytest.mark.parametrize("host,guest,expected", [
        ('rock', 'scissors', 'host'),
        ('scissors', 'paper', 'host'),
        ('paper', 'rock', 'host'),
    ])
    def test_multiple_cases(self, host, guest, expected):
        """Test multiple cases with parametrize."""
        assert determine_winner(host, guest) == expected
```

### Using Fixtures

```python
async def test_with_fixture(client, sample_game):
    """Test using fixtures from conftest.py."""
    # client is an async httpx.AsyncClient wired to the FastAPI app over ASGI
    # sample_game is sample game data
    response = await client.get(f"/game/{sample_game['game_code']}")
    assert response.status_code == 200
```

### Mocking

```python
from unittest.mock import patch

@patch('app.models.Game')
def test_with_mock(mock_game):
    """Test with mocked database."""
    mock_game.get_by_code.return_value = {'id': 'test'}
    # Your test code here
```

## Best Practices

1. **Test Names**: Use descriptive names that explain what is being tested
   - ✅ `test_rock_beats_scissors`
   - ❌ `test_winner`

2. **One Assertion Per Test**: Keep tests focused
   - Each test should verify one behavior

3. **Arrange-Act-Assert Pattern**:
   ```python
   def test_example():
       # Arrange: Set up test data
       game_code = 'ABC123'

       # Act: Perform action
       result = get_game(game_code)

       # Assert: Verify outcome
       assert result is not None
   ```

4. **Use Fixtures**: Reuse common setup with fixtures in `conftest.py`

5. **Mock External Dependencies**: Don't make real API calls or database queries

6. **Test Edge Cases**: Empty inputs, invalid data, boundary conditions

7. **Keep Tests Fast**: Use mocks to avoid slow operations

## Continuous Integration

Add to CI/CD pipeline:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: pytest
```

## Troubleshooting

### Tests Failing Locally

1. Check Python version: `python --version` (requires 3.8+)
2. Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
3. Clear pytest cache: `rm -rf .pytest_cache`
4. Check environment variables are not interfering

### Import Errors

```bash
# Set PYTHONPATH
export PYTHONPATH=$(pwd):$PYTHONPATH
pytest
```

### Database Issues

Tests mock the database by default. If you see database errors, check that mocks are set up correctly in the test.

## Test Metrics

Current coverage targets:
- **Overall**: > 80%
- **Utilities**: > 90%
- **Services**: > 85%
- **Routes**: > 75%

Run `./run_tests.sh coverage` to check current coverage.
