# Development

Welcome to py-moodle development! This guide covers everything you need to contribute to the project.

## Development Setup

### 1. Clone and Setup

```bash
git clone https://github.com/erseco/python-moodle.git
cd py-moodle

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install in development mode
pip install -e .

```

### 2. Development Dependencies

```bash
# Core development tools
pip install black isort flake8 pytest

# Documentation tools
pip install mkdocs mkdocs-material mkdocstrings[python]
```

## Code Style and Standards

### Formatting

The project uses `black` for code formatting and `isort` for import sorting:

```bash
# Format code
make format

# Or manually:
black src/ tests/
isort src/ tests/
```

### Linting

```bash
# Run linter
make lint

# Or manually:
flake8 src/ tests/
```

### Code Standards

- **Language**: All code, comments, and documentation must be in English
- **Docstrings**: Use Google style (enforced by `flake8-docstrings`)
- **Type hints**: Encouraged for new code
- **Line length**: 88 characters (Black default)

Example function with proper docstring:

```python
def create_course(session: requests.Session, url: str, course_data: dict, token: str = None) -> dict:
    """Create a new course in Moodle.
    
    Args:
        session: Authenticated requests session
        url: Base Moodle URL
        course_data: Dictionary containing course information
        token: Optional session token
        
    Returns:
        Dictionary containing the created course information
        
    Raises:
        requests.RequestException: If the request fails
        ValueError: If course_data is invalid
        
    Example:
        >>> course_data = {
        ...     'fullname': 'My Course',
        ...     'shortname': 'my-course',
        ...     'categoryid': 1
        ... }
        >>> course = create_course(session, url, course_data)
        >>> print(course['id'])
        42
    """
    # Implementation here
    pass
```

## Testing

### Running Tests

```bash
# Fast smoke tests that do not require Moodle
make test-unit
pytest tests/unit

# Moodle-backed integration tests (opt in)
make test-local
make test-staging
pytest --integration --moodle-env local -m integration -n auto

# Full local workflow (starts Docker, then runs integration tests)
make test
```

### Writing Tests

- Tests go in the `tests/` directory
- Place fast, Moodle-free coverage in `tests/unit/`
- Integration tests outside `tests/unit/` are automatically marked with
  `@pytest.mark.integration` and skipped unless `--integration` is passed
- Use descriptive test names: `test_create_course_with_valid_data`
- Test both success and failure cases
- Use fixtures from `conftest.py`

### Troubleshooting Test Runs

- `make test-unit` is the fastest way to confirm a change did not break the
  smoke-test layer.
- If an integration run exits before collecting tests, verify the required
  `MOODLE_<ENV>_URL`, `MOODLE_<ENV>_USERNAME`, and `MOODLE_<ENV>_PASSWORD`
  variables exist in `.env`.
- If the `local` integration environment is unreachable, start it with
  `docker compose up -d` or `make upd` before retrying.
- For authentication and session issues during test setup, see
  [Troubleshooting](troubleshooting.md).

Example test:

```python
def test_create_course_success(moodle_session):
    """Test successful course creation."""
    course_data = {
        'fullname': 'Test Course',
        'shortname': 'test-001',
        'categoryid': 1
    }
    
    course = create_course(
        moodle_session.session,
        moodle_session.settings.url,
        course_data,
        token=moodle_session.token
    )
    
    assert course['fullname'] == 'Test Course'
    assert course['shortname'] == 'test-001'
    assert 'id' in course
```

## Project Structure

```
python-moodle/
├── src/py_moodle/          # Main package
│   ├── __init__.py         # Package initialization
│   ├── cli/                # CLI commands
│   │   ├── app.py          # Main CLI app
│   │   ├── courses.py      # Course commands
│   │   └── ...
│   ├── course.py           # Course management
│   ├── session.py          # Session handling
│   └── ...
├── tests/                  # Test suite
├── docs/                   # Documentation
├── Makefile               # Development commands
└── pyproject.toml         # Project configuration
```

## CLI Architecture

The CLI follows a layered architecture:

1. **CLI Layer** (`src/py_moodle/cli/`): Thin command-line interface
2. **Core Library** (`src/py_moodle/`): Core functionality
3. **Session Management** (`session.py`): Authentication and requests

### Adding New CLI Commands

1. **Add core function** to appropriate module (e.g., `course.py`)
2. **Add CLI command** to appropriate CLI module (e.g., `cli/courses.py`)
3. **Add tests** for both core function and CLI command
4. **Update documentation**

Example:

```python
# In src/py_moodle/course.py
def duplicate_course(session, url, course_id, new_name, token=None):
    """Duplicate an existing course."""
    # Implementation
    pass

# In src/py_moodle/cli/courses.py
@courses_app.command("duplicate")
def duplicate_course_cmd(
    course_id: int = typer.Argument(..., help="Course ID to duplicate"),
    new_name: str = typer.Option(..., "--name", help="Name for duplicated course")
):
    """Duplicate a course."""
    ms = MoodleSession.get()
    result = duplicate_course(ms.session, ms.settings.url, course_id, new_name, token=ms.token)
    typer.echo(f"Duplicated course: {result['id']}")
```

### Diagnostics: `--verbose`/`--debug` and secret redaction

The root CLI callback (`src/py_moodle/cli/app.py`) configures the shared
`py_moodle` logger via `py_moodle.cli.output.configure_logging()` based on
the `--verbose`/`--debug` flags:

- Neither flag: the logger stays at `WARNING` (silent for diagnostics).
- `--verbose`/`-v`: the logger is raised to `INFO`, which enables high-level
  milestone messages (e.g. "Logging in to ...", "Login completed: ...").
- `--debug`: the logger is raised to `DEBUG`, which additionally enables
  HTTP-level tracing from `src/py_moodle/auth.py` (requests, status codes,
  response URLs).

All diagnostic output is written to stderr (never stdout), so it never mixes
with the machine-readable payload of `--output json`/`csv`.

When extending `auth.py`'s login/CAS diagnostics, or any other code path that
might log a secret-bearing value:

- Never log a token, sesskey, password, or cookie value directly. Use the
  `_REDACTED` placeholder instead (see the existing `sesskey obtained: %s`
  and `webservice_token obtained: %s` call sites).
- URLs and headers can carry secrets too (e.g. a CAS `ticket=` query
  parameter, or a `Set-Cookie` header). Route them through the
  `_redact_url()`/`_redact_headers()` helpers in `auth.py` before logging.
- Avoid logging raw HTTP response bodies. Moodle pages routinely embed the
  current user's `sesskey` inline (e.g. `M.cfg.sesskey = "..."`), so even a
  short preview of response text can leak it.
- Add or update a unit test in `tests/unit/test_cli_output_formats.py` that
  plants a fake secret value and asserts (via `caplog`) that it never
  appears in the logged output, only a redacted placeholder.

## Documentation

### Building Documentation

```bash
# Build documentation
make docs

# Serve documentation locally
mkdocs serve

# Deploy to GitHub Pages
mkdocs gh-deploy
```

### Adding API Documentation

API documentation is auto-generated from docstrings. To add a new module:

1. **Add module** to `docs/api/` directory
2. **Create markdown file** with mkdocstrings reference:

```markdown
# Module Name

::: py_moodle.module_name
```

3. **Update navigation** in `mkdocs.yml`

## Contributing Guidelines

### Before Submitting

1. **Run tests**: `make test`
2. **Format code**: `make format`
3. **Check linting**: `make lint`
4. **Update docs**: If adding features
5. **Add tests**: For new functionality

### Pull Request Process

1. **Fork** the repository
2. **Create feature branch**: `git checkout -b feature-name`
3. **Make changes** following code standards
4. **Add tests** for new functionality
5. **Update documentation** if needed
6. **Submit pull request** with clear description

### Commit Messages

Use conventional commit format:

```
feat: add course duplication functionality
fix: handle authentication timeout properly
docs: update installation instructions
test: add tests for user management
```

## Release Process

Releases are handled by maintainers:

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md**
3. **Create release tag**
4. **GitHub Actions** handles PyPI publishing

## Getting Help

- **Issues**: Report bugs or request features on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainers at info@ernesto.es

## Development Tools

### Makefile Commands

```bash
make format    # Format code with black and isort
make lint      # Run flake8 linter
make test      # Run pytest
make docs      # Build documentation
make clean     # Clean build artifacts
```

### Environment Variables

For development, you might need additional environment variables:

```env
# In .env.development
MOODLE_LOCAL_URL=http://localhost:8080
MOODLE_LOCAL_USERNAME=admin
MOODLE_LOCAL_PASSWORD=admin
DEBUG=true
```

### Docker Development

Use the provided Docker setup for consistent development:

```bash
# Start Moodle development instance
docker-compose up -d

# Run tests against Docker instance
MOODLE_LOCAL_URL=http://localhost:8080 make test-local
```
