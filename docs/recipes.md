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
