# Quick Start

Get up and running with py-moodle in minutes!

## Prerequisites

- Python 3.8+ installed
- Access to a Moodle instance
- Valid Moodle credentials

## 1. Install py-moodle

```bash
pip install py-moodle
```

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
py-moodle courses list
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
py-moodle courses show 2
```

**Create a new course:**
```bash
py-moodle courses create --fullname "Test Course" --shortname "test-001"
```

**Add content to a course:**
```bash
py-moodle modules add label --course-id 2 --section-id 1 --name "Welcome" --intro "Welcome to the course!"
```

## Next Steps

- Check out the [CLI Reference](../cli.md) for all available commands
- Read the [Configuration](configuration.md) guide for advanced setup
- Browse [API Reference](../api/session.md) to use py-moodle as a library

!!! tip "Need Help?"
    Use `py-moodle --help` or `py-moodle COMMAND --help` for detailed command information.
