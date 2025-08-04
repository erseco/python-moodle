<p align="center">
  <img src="https://raw.githubusercontent.com/erseco/python-moodle/main/docs/images/py-moodle-icon.png" alt="py-moodle logo" width="128">
</p>

# python-moodle

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/erseco/python-moodle/blob/main/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyPI downloads](https://img.shields.io/pypi/dm/python-moodle)](https://pypi.org/project/python-moodle/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub repository](https://img.shields.io/badge/github-repository-blue)](https://github.com/erseco/python-moodle)

> **A modern Pythonic CLI and library to manage Moodle via web sessions, with full session and CAS support.**

!!! warning "Experimental"
    This library is under active development. Use a test Moodle instance and back up data before running commands that create, modify, or delete content.

`py-moodle` allows you to automate tedious Moodle tasks—like creating courses, uploading content, and managing modules—directly from your terminal or in your Python scripts. It works by simulating a real user's web session, so it doesn't require API tokens or special Moodle plugins.

---

## Features

-   **Manage Moodle entities**: Courses, sections, users, and modules from the command line.
-   **Rich module support**: Includes built-in support for Folders, Labels, Assignments, and SCORM packages.
-   **Session-based**: Works with standard Moodle web sessions, avoiding the need for web service tokens.
-   **Authentication**: Supports standard Moodle login and SSO/CAS authentication.
-   **Dual Use**: Can be used as a powerful CLI or imported as a library into your own Python projects.
-   **Extensible**: Designed to be easily extended with new modules and commands. See `AGENTS.md`.
-   **English-only codebase**: For clear, global collaboration.

---

## Installation

You will need Python 3.8+ and `pip`.

### Install from PyPI (Recommended)

```bash
pip install python-moodle
```

### Install from Source

Clone the repository and install:

```bash
git clone https://github.com/erseco/python-moodle.git
cd python-moodle
pip install .
```

### Configure your environment

Copy the example `.env.example` file to `.env` and add your Moodle instance credentials.

```bash
cp .env.example .env
# Now, edit the .env file with your credentials
```

!!! danger
    The `.env` file stores real credentials. Keep it out of version control and share it with no one.

Your `.env` file should look like this:

```env
# Production environment credentials
MOODLE_PROD_URL=https://your.moodle.site
MOODLE_PROD_USERNAME=your_admin_user
MOODLE_PROD_PASSWORD=your_super_secret_password
# Optional: CAS SSO URL
# MOODLE_PROD_CAS_URL=https://cas.your-institution.org/cas
# Optional: Predefined webservice token (required for CAS)
# MOODLE_PROD_WS_TOKEN=your_webservice_token
```

Use the `--env` flag or the `MOODLE_ENV` variable to select the environment, e.g. `py-moodle --env prod courses list`.

> **Note**: For local development, you can quickly spin up a Moodle instance using the provided `docker-compose.yml`: `docker-compose up -d`.

---

## CLI Usage

Once installed, all functionality is available through the `py-moodle` command. Every command and subcommand includes detailed help with the `-h` or `--help` flag.

### Common Commands

Here are a few examples of common commands:

**List all available courses:**

```bash
py-moodle courses list
```

*Output:*

```
┏━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┓
┃ ID ┃ Shortname          ┃ Fullname           ┃ Category ┃ Visible ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━┩
│ 2  │ my-first-course    │ My first course    │ 1        │ 1       │
│ 4  │ my-second-course   │ My second course   │ 1        │ 1       │
└────┴────────────────────┴────────────────────┴──────────┴─────────┘
```

**Show the structure of a single course:**

```bash
py-moodle courses show 2
```

**Create a new course:**

```bash
py-moodle courses create --fullname "My New Automated Course" --shortname "auto-course-01"
```

**Add a label to a course section:**

```bash
py-moodle modules add label --course-id 2 --section-id 1 --name "Welcome" --intro "<h1>Welcome to the course!</h1>"
```

**Upload a SCORM package to a course:**

```bash
py-moodle modules add scorm --course-id 2 --section-id 1 --name "My SCORM Package" --path "path/to/your/scorm.zip"
```

---

## Library Usage (Automation Scripting)

You can also import `py-moodle`'s functions into your own Python scripts to automate complex workflows. The `example_script.py` file provides a comprehensive tutorial.

### Quick Example

```python
from py_moodle import MoodleSession
from py_moodle.course import list_courses

# Credentials are loaded automatically from your .env file
ms = MoodleSession.get()
courses = list_courses(ms.session, ms.settings.url, token=ms.token)
for course in courses:
    print(course["id"], course["fullname"])
```


### How the Example Script Works

The script is a self-contained demonstration that:

1.  Logs into Moodle using the credentials from your `.env` file.
2.  Creates a new, temporary course.
3.  Populates the course with sections, labels, assignments, and a SCORM package.
4.  Creates a folder and uploads multiple files to it.
5.  Prints a summary of the final course structure.
6.  **Automatically cleans up and deletes the course and all its contents.**

### Running the Example

Make sure you have a valid `.env` file and have installed the dependencies. Then, simply run:

```bash
python example_script.py
```

This script is the best starting point for understanding how to use the library's functions for your own automation needs.

---

## Testing

The project uses `pytest` and provides a `Makefile` with convenient targets.

Run the default test suite against the local environment:

```bash
make test-local
```

Run tests against the staging environment:

```bash
make test-staging
```

Run all configured environments:

```bash
make test
```

## Development

Use the Makefile to format code, run linters, or build the documentation:

```bash
make format   # run black and isort
make lint     # run static analysis
make docs     # build the MkDocs site
```

---

## Documentation

Documentation is generated with [MkDocs](https://www.mkdocs.org/) using the Read the Docs theme and published automatically to the `gh-pages` branch.
Every push to `main` builds the API reference and CLI guide from the source code and makes it available via GitHub Pages.

To build the documentation locally:

```bash
pip install mkdocs 'mkdocstrings[python]'
mkdocs build --strict
```

The rendered site will be available under the `site/` directory.

---

## Contribution

Contributions are welcome! Please follow the guidelines outlined in **[AGENTS.md]**. Key principles include:

-   All code, comments, and documentation must be in **English**.
-   Code must be formatted with `black` and linted with `flake8`.
-   Docstrings must use the Google style; `flake8-docstrings` is configured for this convention.
-   The CLI should be a thin layer over the core library functions.
-   All new features must be accompanied by tests.

---

## License

This project is licensed under the [MIT License](./LICENSE).
