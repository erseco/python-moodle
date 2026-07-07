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

## Preview a mutating command with `--dry-run`

`courses create`, `courses delete`, and `modules add scorm` support
`--dry-run` to preview the action's plan without touching Moodle. Combine it
with `--output json` for scripting or CI pipelines that want to validate a
plan before running it for real.

```bash
# Preview a course creation without calling Moodle.
py-moodle courses create \
  --fullname "Automation Demo" \
  --shortname "automation-demo" \
  --dry-run --output json

# Preview a deletion; no confirmation prompt is shown in dry-run mode.
py-moodle courses delete 42 --dry-run --output json

# Preview a SCORM upload without uploading the package.
py-moodle modules add scorm \
  --course-id 2 \
  --section-id 1 \
  --name "SCORM 1" \
  --file ./package.zip \
  --dry-run --output json
```

Each command prints a plan `dict` with `action`, `dry_run`, `target`, and
`parameters` fields. Fields that cannot be known before contacting Moodle
(such as the `course_id` assigned by `courses create`) are marked with a
placeholder value instead of a real ID.

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
