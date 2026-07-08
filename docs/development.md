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

# Documentation tools (Zensical requires Python 3.10+)
pip install zensical mkdocstrings[python]
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

The package is PEP 561 typed: it ships a `py.typed` marker
(`src/py_moodle/py.typed`, packaged via `[tool.setuptools.package-data]` in
`pyproject.toml`), so type checkers such as mypy and pyright pick up the inline
annotations that `py_moodle` already exposes for downstream consumers.

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

### Making HTTP Requests

`src/py_moodle/http.py` centralizes HTTP behavior for talking to Moodle:
default timeouts (from `config.py`), conservative retry-with-backoff for
safe GET-style requests only, typed exceptions (`MoodleHttpError`,
`MoodleTimeoutError`, `MoodleWebserviceError`) instead of raw `requests`
exceptions or `json.JSONDecodeError`, and redaction of secrets (webservice
token, `sesskey`, password, cookies, `Authorization` header) from
exception messages. New code that talks to Moodle should prefer the
helpers in this module (`request_webservice`, `request_html_get`,
`request_form_post`, `request_ajax`, `upload_file`) over calling
`session.get`/`session.post`/`requests.post` directly. Only a few call
sites have been migrated so far (`session.py`'s `MoodleSession.call()` and
`course.py`'s `list_courses()`/`create_course()`); migrating the remaining
modules is tracked as follow-up work.

### Transport Strategies

`src/py_moodle/transport/` formalizes the three ways `py-moodle` talks to
Moodle as explicit, independently testable strategy modules built on top
of `http.py`:

- `transport/webservice.py` — the webservice/REST API transport
  (`{base_url}/webservice/rest/server.php` with a `wstoken`).
- `transport/ajax.py` — the internal AJAX endpoint transport
  (`{base_url}/lib/ajax/service.php?sesskey=...`).
- `transport/html.py` — an interface-only placeholder for a future
  HTML-scraping/form-submission transport (e.g. `course/edit.php`).

Both `webservice.call(...)` and `ajax.call(...)` raise
`transport.TransportUnavailableError` when that specific transport cannot
be used for the call (invalid/expired token, missing `sesskey`), letting a
caller fall back to the next transport in the chain, and
`transport.TransportError` for any other failure. `course.py`'s
`list_courses()` has been migrated as a proof of concept to use these two
transports instead of inlining the webservice/AJAX request-building and
fallback logic itself; migrating the remaining webservice/AJAX call sites
(`get_course_state`, and the AJAX calls in `section.py`, `module.py`,
`draftfile.py`) onto the same transport modules is tracked as follow-up
work.

## Testing

### Test Layers

The suite is split into two clearly separated layers:

- **Unit / smoke tests** live in `tests/unit/`. They never talk to a Moodle
  server, run fast, and are the default gate for every change. Anything under
  `tests/unit/` runs unconditionally.
- **Integration tests** live directly in `tests/` (the `tests/test_*.py`
  modules outside `tests/unit/`). They require a live Moodle instance and are
  opt-in: `conftest.py` automatically marks every test outside `tests/unit/`
  with `@pytest.mark.integration` and *skips* it unless you pass
  `--integration`. When `--integration` is given, the target Moodle
  environment is selected with `--moodle-env` (`local` | `staging` | `prod`)
  and its reachability is verified before collection.

### Running Tests

```bash
# Fast smoke tests that do not require Moodle
make test-unit
pytest tests/unit

# Moodle-backed integration tests (opt in; require a live instance)
make test-local
make test-staging
pytest --integration --moodle-env local -m integration -n auto

# Full local workflow (starts Docker, waits for Moodle, then runs integration tests)
make test
```

`make test-unit` maps to `pytest tests/unit`, and `make test-local` maps to
`pytest --integration --moodle-env local -m integration -n auto` (see the
`Makefile`). Integration runs use `pytest-xdist` (`-n auto`) to parallelize
across worker processes.

### Shared Course-Creation Fixtures

Many integration modules need a throwaway course to operate on. Instead of
each module hand-rolling its own creation helper, `tests/conftest.py` provides
two shared, session-scoped fixtures (consolidated in
[#62](https://github.com/erseco/python-moodle/pull/62)):

- **`create_temporary_course`** — returns a factory
  `create_temporary_course(session, base_url, sesskey, *, prefix, **kwargs) -> dict`.
  It builds a highly-unique `shortname`/`fullname` from `prefix` (plus a random
  suffix), defaults `categoryid=1` and `numsections=1`, creates the course
  **serialized across `pytest-xdist` workers** (see below), and calls
  `pytest.skip(...)` with a clear reason instead of raising if creation fails.
  Any extra keyword arguments are forwarded to the underlying `create_course()`.
- **`course_creation_lock`** — exposes the same cross-process lock as a
  context-manager factory for the rare test that must call `create_course()`
  directly (for example, a regression test that needs a genuine failure to
  fail the test rather than skip it) while still cooperating with the
  serialization used everywhere else.

#### Why course creation is serialized

Moodle's `course/edit.php` form-based creation flow occasionally hits a
database-level race when two courses are created concurrently against the same
instance: a duplicate-key violation on `mdl_context`'s
`(contextlevel, instanceid)` unique constraint, or a stale
"course context does not exist" lookup in a sibling test. This is a
**Moodle-side race, not a python-moodle bug**, but `pytest-xdist`'s `-n auto`
workers trigger it routinely. Because each xdist worker is a separate OS
process, a plain `threading.Lock` would not help; the fixtures use a file lock
(`fcntl.flock`) so serialization holds across processes. Only the brief
creation call itself is serialized, so overall suite parallelism is largely
unaffected.

> **New integration test modules that need a temporary course MUST use the
> shared `create_temporary_course` factory** rather than calling
> `create_course()` directly. This keeps creation serialized (avoiding the
> `mdl_context` race), keeps course names unique across workers, and preserves
> the "skip, don't crash" behavior on setup failure. Do not reintroduce a
> per-file course-creation fixture.

### HTML-Fixture Regression Tests

The version-sensitive HTML parsers in `src/py_moodle/compat.py` (login token,
`sesskey`, folder listings, dashboard version, edit forms) are the most likely
code to break when Moodle changes its markup. Fast, network-free regression
coverage that exercises these parsers against representative HTML **fixture
files** under `tests/unit/` is being added as part of
[#68](https://github.com/erseco/python-moodle/issues/68); once merged, those
tests run inside the ordinary `make test-unit` gate. Refer to that scaffolding
(and its `tests/unit/fixtures/html/` directory) when adding coverage for a new
brittle parser — capture a minimal representative fixture rather than asserting
against a live server.

### CI Expectations

GitHub Actions (`.github/workflows/ci.yml`) runs the unit layer on every
supported Python version and the integration layer against a small matrix of
representative Python/Moodle combinations. To keep a single source of truth,
the authoritative Python and Moodle version numbers live in the **Testing**
section of the project [README](https://github.com/erseco/python-moodle#testing)
rather than being duplicated here.

### Writing Tests

- Tests go in the `tests/` directory
- Place fast, Moodle-free coverage in `tests/unit/`
- Integration tests outside `tests/unit/` are automatically marked with
  `@pytest.mark.integration` and skipped unless `--integration` is passed
- Use descriptive test names: `test_create_course_with_valid_data`
- Test both success and failure cases
- Use fixtures from `conftest.py`; use `create_temporary_course` for any
  integration test that needs a throwaway course

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

Example integration test using the shared factory:

```python
def test_create_course_success(moodle, request, create_temporary_course):
    """Test successful course creation via the shared factory."""
    base_url = request.config.moodle_target.url
    course = create_temporary_course(
        moodle, base_url, moodle.sesskey, prefix="DEMO"
    )

    assert course["shortname"].startswith("DEMO")
    assert "id" in course
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
  response URLs) and from the centralized HTTP layer
  `src/py_moodle/http.py` (the `py_moodle.http` logger traces every request
  it sends as `HTTP <METHOD> <redacted-url> -> <status>`, including retry
  attempts). Only the method, the **redacted** URL, and the response status
  are ever traced — never params, request/response bodies, or headers.

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

The site is built with [Zensical](https://zensical.org/), the actively-maintained
successor to MkDocs from the Material for MkDocs team. It reads the existing
`mkdocs.yml` directly, so no separate config file is needed. Zensical requires
Python 3.10+.

```bash
# Build documentation
make docs

# Serve documentation locally
zensical serve
```

Deployment to GitHub Pages happens automatically via
`.github/workflows/docs.yml` on every push to `main`.

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
