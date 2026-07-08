# Quick Start

Get up and running with python-moodle in minutes!

## Prerequisites

- Python 3.8+ installed
- Access to a Moodle instance
- Valid Moodle credentials

## 1. Install python-moodle

```bash
pip install python-moodle
```

The CLI is then available as `python-moodle` (used in the examples below) or its shorter alias `py-moodle`.

## 2. Configure Credentials

Create a `.env` file with your Moodle credentials:

```bash
cp .env.example .env
```

Edit the `.env` file (replace `PROD` with your target environment name):

```env
MOODLE_PROD_URL=https://your-moodle-site.com
MOODLE_PROD_USERNAME=your-username
MOODLE_PROD_PASSWORD=your-password
# Optional: CAS URL and token
# MOODLE_PROD_CAS_URL=https://cas.your-institution.org/cas
# MOODLE_PROD_WS_TOKEN=your_webservice_token
```

Select this environment by running commands with `--env prod` or by setting `MOODLE_ENV=prod`.

## 3. Test Your Setup

List all available courses:

```bash
python-moodle courses list
```

You should see output like:

```
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID ┃ Shortname                    ┃ Fullname                          ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 2  │ my-first-course              │ My first course                   │
│ 4  │ my-second-course             │ My second course                  │
└────┴──────────────────────────────┴───────────────────────────────────┘
```

## 4. Try Some Commands

**Show course details:**
```bash
python-moodle courses show 2
```

**Create a new course:**
```bash
python-moodle courses create --fullname "Test Course" --shortname "test-001"
```

**Add content to a course:**
```bash
python-moodle modules add label --course-id 2 --section-id 1 --name "Welcome" --intro "Welcome to the course!"
```

## 5. Use python-moodle as a Library

Besides the CLI, python-moodle can be used directly from Python scripts.

The low-level modules (`course.py`, `section.py`, `folder.py`, etc.) expose
plain functions that take `session`, `base_url`, `token` and `sesskey`
explicitly - see [Examples](../examples.md) for that style.

For scripts that call more than one or two functions, `MoodleClient` collapses
that repetition into a single object, created once, with a discoverable
`moodle.courses` / `moodle.sections` / `moodle.scorm` / ... API:

```python
from py_moodle import MoodleClient

with MoodleClient.from_env("prod") as moodle:
    courses = moodle.courses.list()
    print(f"Found {len(courses)} courses")

    course = moodle.courses.create(
        fullname="Automation Demo",
        shortname="automation-demo",
    )

    moodle.labels.add(
        course_id=course["id"],
        section_id=1,
        name="Welcome",
        html="<p>Welcome to the course.</p>",
    )
```

`MoodleClient.from_env("prod")` reuses the same `MOODLE_PROD_*` environment
variables configured in step 2, and the same cached, thread-safe session as
`MoodleSession.get("prod")`. The `with` block closes the underlying HTTP
session automatically on exit.

See the [Client API Reference](../api/client.md) for the full list of
resource namespaces.

## Next Steps

- Check out the [CLI Reference](../cli.md) for all available commands
- Read the [Configuration](configuration.md) guide for advanced setup
- Browse [API Reference](../api/client.md) to use python-moodle as a library

!!! tip "Need Help?"
    Use `python-moodle --help` or `python-moodle COMMAND --help` for detailed command information.
