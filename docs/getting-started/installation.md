# Installation

py-moodle requires Python 3.8+ and can be installed in several ways.

## Method 1: PyPI (Recommended)

```bash
pip install py-moodle
```

## Method 2: From Source

Clone the repository and install:

```bash
git clone https://github.com/erseco/python-moodle.git
cd py-moodle
pip install .
```

This makes the `py-moodle` command available system-wide.

## Method 3: Development Installation

For development or to get the latest features:

```bash
git clone https://github.com/erseco/python-moodle.git
cd py-moodle
pip install -e .
```

The `-e` flag installs in "editable" mode, so changes to the source code are immediately available.

## Verify Installation

Test that py-moodle is properly installed:

```bash
py-moodle --help
```

You should see the main help screen with available commands.

## Next Steps

- [Configure your Moodle credentials](configuration.md)
- [Try your first commands](quickstart.md)
