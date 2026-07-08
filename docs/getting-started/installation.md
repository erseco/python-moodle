# Installation

`python-moodle` requires Python 3.9+ and can be installed in several ways.

!!! note "Package name vs. command name"
    The package is published as **`python-moodle`** (that's what you `pip install`
    and `import py_moodle`), and the CLI is available under **two equivalent
    command names**: **`py-moodle`** and **`python-moodle`**. Use whichever you
    prefer — every example in these docs uses `py-moodle`.

## Method 1: PyPI (Recommended)

```bash
pip install python-moodle
```

## Method 2: From Source

Clone the repository and install:

```bash
git clone https://github.com/erseco/python-moodle.git
cd python-moodle
pip install .
```

This makes the `py-moodle` (and `python-moodle`) command available system-wide.

## Method 3: Development Installation

For development or to get the latest features:

```bash
git clone https://github.com/erseco/python-moodle.git
cd python-moodle
pip install -e .
```

The `-e` flag installs in "editable" mode, so changes to the source code are immediately available.

## Verify Installation

Test that the CLI is properly installed (either command works):

```bash
py-moodle --help
# or, equivalently:
python-moodle --help
```

You should see the main help screen with available commands.

## Next Steps

- [Configure your Moodle credentials](configuration.md)
- [Try your first commands](quickstart.md)
