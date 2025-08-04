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
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   └── ...         # CLI modules
│       ├── auth.py
│       ├── course.py
│       ├── folder.py
│       ├── label.py
│       ├── scorm.py
│       ├── draftfile.py
│       └── ...         # Other modules
├── tests/
│   ├── test_auth.py
│   ├── test_course.py
│   └── ...             # One test file per module
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
```

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
* **Structure commands into sub-applications.** For each major entity (e.g., `courses`, `users`), create a separate file in the `commands/` directory (e.g., `commands/courses.py`) containing a `typer.Typer()` app. This keeps the main `cli.py` clean.
* All CLI options and commands must map to functions in the `py_moodle` library.
* CLI help and error messages must be concise, explicit, and in English.

### Environment and Secrets

* Never hardcode secrets or credentials.
* Use `python-dotenv` and load `.env` automatically (see `.env.example`).
* Support the following (minimum) environment variables:

  * `MOODLE_URL`
  * `MOODLE_USERNAME`
  * `MOODLE_PASSWORD`
  * (Optionally) `CAS_URL` for CAS SSO

### Testing

* Place all tests in the `tests/` directory.
* Use [pytest](https://pytest.readthedocs.io/) as the default runner.
* Mock HTTP requests when possible; use sandbox sites for integration.
* Provide at least one test per public function.
* **Test** all supported Moodle versions (see `.env.example` for sandboxes):

  * [https://sandbox.moodledemo.net/](https://sandbox.moodledemo.net/)
  * [https://sandbox405.moodledemo.net/](https://sandbox405.moodledemo.net/)

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

* Each new Moodle entity (e.g., `quiz`, `assign`) should have its own file in the `py_moodle/` directory (e.g., `py_moodle/quiz.py`) and a corresponding test file (`tests/test_quiz.py`).
* All module functions must be designed for both CLI use and programmatic import.
* To add a new command group (e.g., for `quiz`):
  1.  Create a new file `commands/quiz.py`.
  2.  Inside, define a `typer.Typer()` app: `app = typer.Typer(help="Manage quizzes.")`.
  3.  Add commands to this new app (e.g., `@app.command("list")`).
  4.  In `cli.py`, import the app and add it: `from commands import quiz; app.add_typer(quiz.app, name="quizzes")`.
  5.  Implement the core logic in `py_moodle/quiz.py` and call it from your command function.
  6.  Write at least one test for the new function in `tests/test_quiz.py`.

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

2.  **Define the command in `commands/courses.py`:**

    ```python
    # commands/courses.py
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
        course = create_course(ms.session, fullname, shortname)
        typer.echo(f"Course created: {course['id']}")
    ```

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
MOODLE_URL=https://sandbox.moodledemo.net
MOODLE_USERNAME=admin
MOODLE_PASSWORD=sandbox24
# CAS_URL=https://cas.your-institution.org/cas
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

