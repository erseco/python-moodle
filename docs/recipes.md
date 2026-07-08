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

## Diagnosing a broken environment

Use `doctor` when `site info` (or any other command) fails and you need to
know exactly which part of the environment is misconfigured: base URL,
login, sesskey, webservice token, webservice reachability, upload endpoint,
and a few other derived facts.

```bash
py-moodle --env prod doctor run
```

Machine-readable output is useful in CI or before running bulk operations:

```bash
py-moodle --env prod doctor run --output json
```

Each row is one independent check with a `pass`, `warn`, or `fail` status:

- `fail` means a **critical** check did not pass (base URL unreachable, login
  failed, or no sesskey available). `doctor` exits with code `1`.
- `warn` means an optional check could not be completed (for example, no
  webservice token configured) but the environment is still usable for the
  operations that do not depend on it. `doctor` still exits with code `0`.
- An unknown or misconfigured `--env` (missing required `MOODLE_<ENV>_*`
  variables) is reported before any check runs, and `doctor` exits with
  code `2`.

`doctor` never prints raw secret values (password, webservice token, or
sesskey); check messages only report presence, length, or other
non-sensitive derived facts.

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

## Select only the fields you need with `--fields`

The `courses`, `categories`, `sections`, and `users` `list` commands accept
`--fields field1,field2,...` to project the machine-readable output
(`--output json`/`yaml`/`csv`) down to just the fields you want, in the order
you list them. This avoids a post-processing step with `jq`/`cut` and gives
you a stable, minimal shape for automation.

```bash
# Only the id and shortname of every course, as JSON, in that order.
py-moodle courses list --output json --fields id,shortname

# The same projection as CSV (the selected fields become the columns).
py-moodle courses list --output csv --fields id,shortname > courses.csv

# Field order follows what you pass, so this puts shortname first.
py-moodle courses list --output json --fields shortname,id
```

Notes:

- `--fields` only affects machine-readable output; it is ignored for the
  default `--output table`.
- An unknown field name is a hard error (non-zero exit, the offending field
  and the available fields are printed to stderr), so a typo fails loudly
  instead of silently returning empty columns.
- Passing an empty value (`--fields ""`) is treated as "no filtering",
  identical to omitting the flag.

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

### Equivalent recipe using `MoodleClient`

The same workflow, scripted with the [`MoodleClient`](api/client.md) facade
instead of the CLI:

```python
from py_moodle import MoodleClient

with MoodleClient.from_env("prod") as moodle:
    course = moodle.courses.create(
        fullname="Automation Demo",
        shortname="automation-demo",
    )
    section = moodle.sections.create(course["id"])
    moodle.labels.add(
        course_id=course["id"],
        section_id=section.get("section", 1),
        name="Welcome",
        html="<p>Welcome to the course.</p>",
    )
```

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

## Idempotent provisioning: ensure a course exists

Use `courses ensure` in CI pipelines or onboarding scripts that need to
provision a course without failing (or creating duplicates) on repeat runs.

```bash
# Safe to run every time: creates the course only if it is missing.
py-moodle courses ensure \
  --shortname "ci-smoke-test" \
  --fullname "CI Smoke Test" \
  --category-id 1
```

Re-running the same command reports `status: reused` instead of failing with
a "shortname already in use" error. If the course already exists with a
different `--fullname`/`--category-id`, the command reports
`status: conflict` (and exits with code `1`) without changing anything,
letting you inspect the `differences` before deciding what to do:

```bash
py-moodle courses ensure \
  --shortname "ci-smoke-test" \
  --fullname "Renamed CI Smoke Test" \
  --category-id 1 \
  --output json
```

Pass `--update` to have the command bring `fullname`/`--category-id` in line
with the request instead of reporting a conflict:

```bash
py-moodle courses ensure \
  --shortname "ci-smoke-test" \
  --fullname "Renamed CI Smoke Test" \
  --category-id 1 \
  --update
```

`--update` only ever touches `fullname` and category membership; it never
overwrites the course summary, visibility, or its sections/modules.

## Get IDE-friendly typed models from raw dicts (optional)

The library functions keep returning plain `dict`/`list[dict]` values, but
`py_moodle.models` offers opt-in typed wrappers if you want autocompletion
and static-typing safety in your own scripts.

```python
from py_moodle import MoodleSession
from py_moodle.course import list_courses
from py_moodle.models import Course

ms = MoodleSession.get()

for raw_course in list_courses(ms.session, ms.settings.url, token=ms.token):
    typed_course = Course.from_moodle(raw_course)
    print(typed_course.id, typed_course.fullname)
```

`Course.from_moodle()` (and the other `from_moodle()` classmethods) tolerate
missing optional fields and ignore unknown/extra keys, so they are safe to
use even as the underlying Moodle payload shape drifts across versions.

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
