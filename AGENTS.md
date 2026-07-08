# AGENTS.md

## Purpose

This document provides **implementation and contribution guidelines** for developing new features, modules, or commands within the `py-moodle` project.
It is designed for both human developers and AI agents that will generate, review, or maintain code in this repository.

---

## General Philosophy

* **Write everything in English:**
  All code, docstrings, function names, variable names, and code comments **MUST** be written in English, regardless of the language of user requests or documentation.
* **Pythonic by design:**
  Code must follow the [PEP8](https://peps.python.org/pep-0008/) style guide. Prioritize clarity, modularity, and explicitness.
* **CLI-first and library-ready:**
  The CLI (`cli.py`) should be a thin layer over importable Python modules. Every CLI command should map directly to a public function in the corresponding module.
* **Testability:**
  All features must be accompanied by simple, readable unit tests (in `tests/`). Use real Moodle sandboxes when needed, but support mocking.
* **Extensibility:**
  Structure code so that new module types (e.g., quiz, assign) can be added with minimal coupling.

---

## Project Structure

```
python-moodle/
├── src/
│   └── py_moodle/
│       ├── __init__.py         # Re-exports MoodleClient, models, MoodleSession, Settings
│       ├── __main__.py
│       ├── py.typed            # PEP 561 marker (the package ships type information)
│       ├── cli/                # Typer CLI layer (thin wrappers over the library)
│       │   ├── app.py          # Root Typer app + global flags (--output/--quiet/--verbose/...)
│       │   ├── output.py       # OutputFormat, emit(), --fields, console + logging helpers
│       │   ├── courses.py, sections.py, modules.py, users.py, categories.py,
│       │   ├── folders.py, pages.py, resources.py, urls.py, site.py, doctor.py, admin.py
│       ├── client.py           # MoodleClient facade (courses/sections/modules/... namespaces)
│       ├── session.py          # MoodleSession: cached auth + token/sesskey
│       ├── auth.py             # login / CAS SSO (redacted --debug tracing)
│       ├── http.py             # Centralized requests: timeouts, bounded GET retry, redaction, tracing
│       ├── transport/          # webservice.py / ajax.py / html.py strategies
│       ├── compat.py           # Version-sensitive HTML parsing strategies (4.x/5.x)
│       ├── config.py           # Shared HTTP timeout policy
│       ├── models.py           # Typed dataclasses: Course, CourseSection, CourseModule, User, ...
│       ├── ensure.py           # Idempotent ensure_module/label/resource/folder/section
│       ├── doctor.py           # Environment self-diagnostics
│       ├── course.py, section.py, label.py, resource.py, folder.py, page.py,
│       ├── url.py, module.py, user.py, category.py, scorm.py, draftfile.py,
│       ├── upload.py, permissions.py, settings.py, site.py, assign.py
├── tests/
│   ├── unit/                   # No Moodle needed; run in CI on every push (make test-unit)
│   │   ├── fixtures/html/       # Captured HTML for compat-parser regression tests
│   │   └── test_*.py
│   ├── conftest.py             # Shared fixtures: create_temporary_course, course_creation_lock, login warmup
│   ├── test_course.py, ...     # Integration tests (need --integration + a live Moodle)
├── docs/                       # MkDocs/Zensical site (recipes.md, api/, roadmap-plan.md, ...)
├── README.md, LICENSE, pyproject.toml, .env.example, docker-compose.yml, Makefile
```

---

## Architecture (current layering)

New code MUST fit this layering — do not call `requests`/`session.get` directly from
feature modules, and do not put Moodle logic in the CLI.

1. **CLI layer (`cli/`)** — Typer sub-apps, one file per entity, each command a thin
   wrapper that calls a public library function and renders via `cli/output.py`.
   * Machine-readable output is unified: every `list` command supports
     `--output table|json|yaml|csv` and `--fields field1,field2` (order-preserving
     projection for json/yaml/csv). Use `emit(data, output_format, table_fn=..., csv_fields=..., fields=...)`.
   * Global flags on the root app: `--quiet`, `--no-color` (also `NO_COLOR`),
     `--verbose`/`-v` (INFO), `--debug` (DEBUG). Diagnostics go to **stderr** only, so
     they never contaminate `--output json`/`csv` on stdout.
2. **Library layer** — one module per Moodle entity (`course.py`, `section.py`, `label.py`,
   `resource.py`, `folder.py`, `page.py`, `url.py`, `module.py`, `user.py`, `category.py`,
   `scorm.py`, `draftfile.py`, `upload.py`). Every public function is import-friendly and
   CLI-agnostic, takes an explicit `session`/`base_url`/`sesskey`, and raises a typed
   `Moodle<Entity>Error`.
3. **HTTP / transport layer** — all new HTTP goes through `http.py`
   (`request_webservice`/`request_html_get`/`request_form_post`/`request_ajax`/`upload_file`):
   it applies the shared timeout policy from `config.py`, retries **only** idempotent
   GET-style requests with bounded backoff (mutations are never auto-retried), redacts
   secrets from any exception message, and emits redacted `DEBUG` request traces on the
   `py_moodle.http` logger. `transport/` splits the webservice / AJAX / HTML strategies;
   `compat.py` centralizes version-sensitive HTML parsing (add fixtures under
   `tests/unit/fixtures/html/` when you touch it).
4. **High-level API** — `client.py` (`MoodleClient` facade with `.courses`, `.sections`,
   `.modules`, ... namespaces), `models.py` (typed dataclasses with `from_dict`), `doctor.py`.
5. **Idempotent provisioning** — prefer the ensure-style API for "make it exist" flows:
   `ensure_course`/`create_or_update_course` (`course.py`) and
   `ensure_module`/`ensure_label`/`ensure_resource`/`ensure_folder`/`ensure_section`
   (`ensure.py`). Each keys on a natural identifier (shortname / `(name, modname)` /
   section name) and returns a typed `Ensure*Result` with a `status`
   (`created`/`reused`/`updated`/`conflict`).

---

## Conventions & Best Practices

### Coding

* **Always** write code and comments in English, even if the user, ticket, or prompt is in another language.
* Use function docstrings to describe *what* and *why*.
* Format all docstrings using the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
  `flake8-docstrings` is configured with `docstring-convention=google` to check this style.
* Prefer [type hints](https://peps.python.org/pep-0484/).
* Functions should be short, focused, and testable.
* For code that interacts with Moodle:

  * Use `requests.Session()` for all HTTP communication.
  * Parse HTML with `BeautifulSoup('lxml')` where needed.
  * Modularize every logical area: `auth.py` for login/session, `course.py` for course listing, etc.

* **When returning a list of items (e.g., courses), the default order must always be by `id` ascending.**  
  All course listings and similar outputs must be sorted by `id` before being returned or displayed.
* **All tabular CLI output should use the [`rich`](https://rich.readthedocs.io/) library for formatting if available.**  
  If `rich` is not installed, fall back to a plain text table. All new CLI table outputs must use `rich` unless there is a strong reason not to.

### CLI

* Use [typer](https://typer.tiangolo.com/) to define the CLI.
* **Structure commands into sub-applications.** For each major entity (e.g., `courses`,
  `users`), there is a file in the `src/py_moodle/cli/` package (e.g.
  `cli/courses.py`) containing a `typer.Typer()` app, wired into the root app in
  `cli/app.py`. This keeps the root app clean.
* All CLI options and commands must map to functions in the `py_moodle` library — the
  command function resolves a `MoodleSession` (`MoodleSession.get(ctx.obj["env"])`),
  calls the library function, and renders through `cli/output.py`'s `emit()`.
* Reuse the shared output plumbing: `--output`, `--fields`, `--quiet`/`--no-color`
  (via `get_console(ctx)`), and `--verbose`/`--debug` (via `configure_logging`). Do not
  hand-roll JSON/CSV formatting or `print()` in a command.
* CLI help and error messages must be concise, explicit, and in English. Never `print()`
  a secret; diagnostics use the `py_moodle*` loggers, which redact tokens/sesskeys/passwords.

### Environment and Secrets

* Never hardcode secrets or credentials.
* Use `python-dotenv` and load `.env` automatically (see `.env.example`).
* Credentials are grouped per named environment (`local`, `staging`, `prod`), selected
  with the CLI `--env`/`--moodle-env` option; each uses a prefix:

  * `MOODLE_<ENV>_URL`
  * `MOODLE_<ENV>_USERNAME`
  * `MOODLE_<ENV>_PASSWORD`
  * `MOODLE_<ENV>_WS_TOKEN` (optional webservice token)
  * (Optionally) a CAS URL for CAS SSO

  The Docker integration container is the `local` environment (`http://localhost`).

### Testing

The suite has two layers (see `docs/development.md` for the full contract):

* **Unit tests — `tests/unit/`**: no Moodle instance, no network, no Docker. They run
  on every push across Python 3.9–3.13 (`make test-unit` / `pytest tests/unit`). New
  behavior in the library, CLI, `http.py`, transports, or `compat.py` MUST have unit
  tests here, mocking HTTP with the `StubSession`/`StubResponse` patterns already in
  `tests/unit/test_http.py` / `test_transport.py`. Brittle HTML parsing is covered by
  fixture files in `tests/unit/fixtures/html/` (`test_html_fixtures.py`).
* **Integration tests — `tests/test_*.py`**: require `--integration` and a live Moodle,
  provided in CI by a Dockerized [`erseco/alpine-moodle`](https://github.com/erseco/alpine-moodle)
  container (`make test-local`, or `pytest --integration --moodle-env local -m integration -n auto`).
  The CI matrix exercises Moodle 4.5.5 / 5.0.1 / 5.1.5.

Rules for integration tests:

* A temporary course MUST be created through the shared **`create_temporary_course`**
  factory fixture (or the `course_creation_lock`) in `tests/conftest.py` — never call
  `create_course()` directly from a new fixture. Course creation is serialized across
  `pytest-xdist` workers to avoid a Moodle-side context race; a per-session login
  warmup absorbs the post-boot login race.
* Reliable CI gates are `unit` / `lint` / `docs` / `CodeQL`. The Docker `integration`
  legs are occasionally flaky under parallel execution; a failed leg is usually cleared
  with `gh run rerun --failed`, not a code change.
* Provide at least one test per public function; prefer fast mocked unit tests, and add
  an integration test only when the behavior genuinely needs a live Moodle.

---

## Supported Commands and Features

The CLI uses a subcommand structure. For example, `py-moodle courses list`.

```sh
# List all courses
py-moodle courses list

# Show details for a specific course
py-moodle courses show <course-id>

# Create a new course
py-moodle courses create --fullname "My New Course" --shortname "mynewcourse"

# Delete a course
py-moodle courses delete <course-id>

# Add a new label to a course section
py-moodle modules add label <course-id> <section-id> --name "My Label" --intro "Label content"
```

### Capabilities and Webservice Limitations

Some Moodle webservice functions require specific capabilities and must be enabled in the external service configuration. For example:

- `core_course_create_categories` requires `moodle/category:manage` and must be enabled in the webservice.
- If your token does not have the required capability, you will get an "Access control exception".
- If the function is not available in your webservice, you must use the legacy AJAX endpoints for those actions.

**If you cannot create or delete categories via webservice, the CLI will fallback to the legacy AJAX endpoints.**

This style should be extended to other modules (`folder`, `scorm`, ...).

---

## Authentication

* Always authenticate using web session, never Selenium or official API tokens.
* Support CAS/SSO if configured via `.env`.
* Persist session cookies for re-use across CLI invocations (store in-memory or on disk if appropriate).
* Raise explicit errors for login failures, missing tokens, or session expiry.

---

## Extending the CLI

* Each new Moodle entity (e.g., `quiz`, `assign`) should have its own module in
  `src/py_moodle/` (e.g., `src/py_moodle/quiz.py`) with a unit test in `tests/unit/`.
* All module functions must be designed for both CLI use and programmatic import.
* To add a new command group (e.g., for `quiz`):
  1.  Create `src/py_moodle/cli/quiz.py`.
  2.  Inside, define a `typer.Typer()` app: `app = typer.Typer(help="Manage quizzes.")`.
  3.  Add commands (e.g., `@app.command("list")`), rendering via `emit()` and honoring
      `--output`/`--fields`.
  4.  In `src/py_moodle/cli/app.py`, import and register it:
      `from . import quiz; app.add_typer(quiz.app, name="quizzes")`.
  5.  Implement the core logic in `src/py_moodle/quiz.py` (HTTP via `http.py`) and call it
      from the command.
  6.  Add unit tests in `tests/unit/` (mocked) and, if it needs a live Moodle, an
      integration test using the shared `create_temporary_course` fixture.

---

## Example: Adding a `courses create` Command

1.  **Implement the logic in `py_moodle/course.py`:**

    ```python
    # py_moodle/course.py
    def create_course(session: requests.Session, fullname: str, shortname: str) -> dict:
        """Creates a new course."""
        # ... implementation ...
        return course_data
    ```

2.  **Define the command in `src/py_moodle/cli/courses.py`:**

    ```python
    # src/py_moodle/cli/courses.py
    import typer
    from py_moodle.course import create_course
    from py_moodle.session import MoodleSession

    app = typer.Typer(help="Manage courses.")

    @app.command("create")
    def create_new_course(
        ctx: typer.Context,
        fullname: str = typer.Option(..., "--fullname"),
        shortname: str = typer.Option(..., "--shortname"),
    ):
        """Creates a new course."""
        ms = MoodleSession.get(ctx.obj["env"])
        course = create_course(
            ms.session, ms.settings.url, ms.sesskey,
            fullname=fullname, shortname=shortname, categoryid=1,
        )
        typer.echo(f"Course created: {course['id']}")
    ```

    (Registered in `cli/app.py` via `app.add_typer(courses.app, name="courses")`.)

3.  **Add a test in `tests/test_course.py`:**

    ```python
    # tests/test_course.py
    def test_create_course():
        # ... test implementation ...
    ```

---

## Internationalization

> **MANDATORY:**
> Even if a user requests something in Spanish (or any other language), all code, docstrings, and comments **MUST** be in English.
>
> When generating code or documentation, always answer in English unless the instruction is explicitly to translate output (not code).

---

## Contribution & Style

* All code must pass `flake8` or similar linter, and be autoformatted (e.g., with `black`).
* Use 4 spaces for indentation.
* Keep dependencies minimal; prefer standard library when possible.
* Write code as if others (or an AI agent) will extend it.

---

## Example .env.example

```
# Per-environment credentials, selected with --env local|staging|prod
MOODLE_LOCAL_URL=http://localhost
MOODLE_LOCAL_USERNAME=moodleuser
MOODLE_LOCAL_PASSWORD=PLEASE_CHANGEME

MOODLE_STAGING_URL=https://sandbox.moodledemo.net
MOODLE_STAGING_USERNAME=admin
MOODLE_STAGING_PASSWORD=sandbox24

MOODLE_PROD_URL=https://your.moodle.site
MOODLE_PROD_USERNAME=your_admin_user
MOODLE_PROD_PASSWORD=***
MOODLE_PROD_WS_TOKEN=***
```

---

## References

* [Moodle AJAX internals](https://moodledev.io/docs/apis/core/ajax)
* [click documentation](https://click.palletsprojects.com/)
* [python-dotenv](https://github.com/theskumar/python-dotenv)
* [BeautifulSoup docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
* [requests docs](https://docs.python-requests.org/)

---

## Naming

The project name is `py-moodle`. If you later publish to PyPI, ensure the name does not clash with Selenium- or API token-based Moodle tools.

---

## Last Notes

* All features should be easy to use and maintain, focusing on developer and user experience.
* Keep the codebase modular: **one module, one responsibility**.
* Document all public functions with meaningful docstrings.
* Provide help output (`--help`) for every CLI command.
* Design all code to be testable, extensible, and robust to future Moodle changes.

---

**If you have doubts about how to implement a feature, prefer explicit, modular code and clear documentation. Always code and comment in English.**

