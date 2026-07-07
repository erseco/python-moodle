# MoodleClient

`MoodleClient` is a high-level, discoverable facade over the function-based
`py_moodle` modules. It owns a connected Moodle session and exposes grouped
resource namespaces (`courses`, `sections`, `users`, `folders`, `labels`,
`assignments`, `scorm`) instead of requiring every call site to thread
`session`, `base_url`, `token` and `sesskey` by hand.

It is a pure facade: every resource-namespace method delegates to the
existing, already-documented functions in `course.py`, `section.py`,
`user.py`, `folder.py`, `label.py`, `assign.py` and `scorm.py`, without
changing their signatures or behavior.

::: py_moodle.client
