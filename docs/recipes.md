# Recipes

This page collects task-oriented workflows for common `py-moodle` jobs.
Use these recipes when you want a copy/paste starting point instead of a full
command reference.

## Verify your environment and login

Use this recipe first when setting up a new `.env` profile or switching to a
different Moodle environment.

```bash
# Use the environment from MOODLE_ENV or pass one explicitly.
py-moodle --env local site info
```

If the command succeeds, your credentials, session bootstrap, and base URL are
working together.

If it fails:

- confirm the selected environment name matches your `.env` keys
- verify `MOODLE_<ENV>_URL`, `MOODLE_<ENV>_USERNAME`, and
  `MOODLE_<ENV>_PASSWORD`
- review the [Troubleshooting](troubleshooting.md) guide for common login and
  session failures

## Inspect a course before changing it

Use these commands together when you need to confirm IDs and current state
before creating or deleting content.

```bash
# Find the course ID you want to work with.
py-moodle courses list

# Inspect one course in detail.
py-moodle courses show 2

# List its sections before adding modules.
py-moodle sections list 2
```

This flow is useful for scripts and manual operations because it reduces the
chance of targeting the wrong course or section.

## Export data for spreadsheets or shell pipelines

`courses`, `categories`, `sections`, and `users` `list` commands accept
`--output csv`, in addition to the existing `table`, `json`, and `yaml`
formats. CSV output is written to stdout only (no banners or extra text), so
it can be redirected straight into a file or another tool.

```bash
# Save the course list as a CSV file for a spreadsheet.
py-moodle courses list --output csv > courses.csv

# Pipe user emails into another shell tool.
py-moodle users list --course-id 2 --output csv | cut -d, -f3
```

## Automate `py-moodle` in scripts and CI jobs

Combine `--quiet`, `--no-color`, and `--output csv`/`--output json` to keep
automated output clean and machine-readable. `--quiet` suppresses incidental
status/confirmation messages (the command's result and any errors are always
shown); `--no-color` (also respected via the `NO_COLOR` environment variable)
strips ANSI styling from table output.

```bash
# A CI-friendly invocation: no banners, no color, CSV on stdout.
py-moodle --quiet --no-color courses list --output csv

# Diagnose a failing login without leaking secrets into logs: tokens,
# session keys, and passwords are always redacted from --verbose/--debug
# output.
py-moodle --debug site info
```

Errors are always written to stderr, never mixed into `--output json`/`csv`
stdout, so `courses=$(py-moodle courses list --output json)` is safe to use
even when the command fails.

## Create a course and add a welcome label

This is a minimal end-to-end content bootstrap workflow.

```bash
# 1. Create the course.
py-moodle courses create \
  --fullname "Automation Demo" \
  --shortname "automation-demo"

# 2. Create a section if you need one beyond the default course layout.
py-moodle sections create 2 --name "Getting Started"

# 3. Add a welcome label to the first section.
py-moodle modules add label \
  --course-id 2 \
  --section-id 1 \
  --name "Welcome" \
  --intro "<p>Welcome to the course.</p>"
```

Replace the example course ID with the ID returned by the create command in
your environment.

## Upload materials into a folder

Use the dedicated folder commands when you want to manage a reusable course
materials area.

```bash
# Create a folder activity in the course.
py-moodle folders add \
  --course-id 2 \
  --section-id 1 \
  --name "Course Materials"

# Upload a file into the folder activity.
py-moodle folders add-file 15 ./docs/syllabus.pdf

# Confirm the folder contents.
py-moodle folders list-content 15
```

In this recipe, `15` is the folder module ID returned by the add command.

## Run the fastest contributor validation loop

When you are changing code or documentation, this sequence gives the quickest
feedback with the existing repository tooling.

```bash
# Fast smoke tests with no live Moodle requirement.
make test-unit

# Static checks used by CI.
make lint

# Rebuild the documentation site, including generated CLI docs.
make docs
```

Use `make test-local` only when you need Docker-backed integration coverage
against the local Moodle environment.
