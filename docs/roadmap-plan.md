# Improvement Roadmap Execution Plan

This document converts the roadmap checklist into a prioritized, dependency-aware
execution plan based on the current repository state.

## Current Technical Baseline

The roadmap should build on the repository as it exists today rather than
restart work that is already partially done.

- **Package layout is already modular.** The main public library entry points are
  `py_moodle.MoodleSession`, `py_moodle.MoodleSessionError`,
  `py_moodle.Settings`, and `py_moodle.load_settings`
  (`src/py_moodle/__init__.py`). The largest and most central modules are
  `src/py_moodle/module.py`, `src/py_moodle/course.py`, `src/py_moodle/auth.py`,
  and `src/py_moodle/compat.py`.
- **The CLI already has a clear command structure.** `src/py_moodle/cli/app.py`
  registers Typer sub-apps for courses, categories, sections, modules, users,
  admin, folders, pages, resources, URLs, and site info.
- **Tests already have an initial layer split.** `tests/unit/` contains the fast
  smoke tests, while the rest of the suite is automatically marked as
  integration and skipped unless `--integration` is used (`tests/conftest.py`).
- **CI already covers the supported Python versions.** The unit test matrix in
  `.github/workflows/ci.yml` runs on Python 3.8 through 3.13, and integration
  coverage spans Moodle 4.5.5 and 5.0.1.
- **Version-sensitive parsing already has a foothold.**
  `src/py_moodle/compat.py` centralizes Moodle-version detection and selector
  strategies, and session bootstrap wires compatibility state into login flows.
- **Documentation already has a contributor home.** MkDocs builds from `docs/`,
  with `docs/development.md` acting as the main contributor guide.

### Priority Risk Areas

The highest-value next changes are the ones that improve safety and
maintainability without forcing broad refactors.

1. **CLI output remains mostly human-first.** Commands generally expose a
   `--json` flag, but there is no unified `--output` contract, no YAML mode, and
   no field filtering for scripting workflows.
2. **Timeouts are hardcoded and inconsistent.** HTTP operations use several
   different timeout values across modules instead of a centralized policy.
3. **Retry behavior is effectively absent.** Transient network failures are
   mostly surfaced immediately.
4. **Logging and debugging are still ad hoc.** There is no project-wide logging
   strategy, and the current debug behavior is not yet a redacted tracing
   system.
5. **Dict-heavy boundaries are still concentrated in core flows.**
   `course.py`, `module.py`, `upload.py`, and `draftfile.py` still exchange
   large `dict[str, Any]` payloads and return values.
6. **The module architecture still has extension cost.** The repository already
   supports several Moodle module types, but the registration and dispatch story
   is still implicit.

## Prioritized Execution Plan

The sequence below starts with the smallest changes that reduce risk and unlock
later work.

### Progress update (2026-07-08)

The phased plan below is the original forward-looking design and is kept intact
for reference. This section records what has actually landed so far, so the
plan can be read against reality.

**Done:**

- **Phase A** — Subtask 1 (this roadmap document), Subtask 2 (CI matrix now
  covers Moodle 4.5.5 / 5.0.1 / 5.1.5 across Python 3.9–3.13), Subtask 3
  (test-layer & shared-fixture docs, #67/#69), Subtask 25 (HTML-fixture
  regression scaffolding, #68/#70), Subtask 10 (task-oriented recipes,
  including the `--fields` recipe).
- **Phase B** — Subtask 4 (`--output table|json|yaml`, plus `csv`, #25/#55),
  Subtask 5 (`--fields` machine-readable field selection, #66/#71).
- **Phase C** — Subtask 6 (exception wording + `troubleshooting.md`, first
  pass, #23), Subtask 7 (redacted `--debug` HTTP tracing, in `auth.py` and the
  centralized `http.py` layer), Subtask 8 (centralized timeout policy in
  `config.py`, #22/#39), Subtask 9 (bounded, backoff retry for idempotent
  GET-style requests only — mutations are never auto-retried, #39).
- **Phase D** — Subtask 12/13 (typed `Course`, `CourseSection`,
  `CourseModule`, `User`, `UploadResult` dataclasses in `models.py`), plus the
  `MoodleClient` facade, `doctor`, and `ensure_course`/dry-run work
  (#37–#57, #62, #64).
- **Phase G** — Subtask 15 (`--dry-run` for mutating commands),
  partial Subtask 16 (`--force` / `ConfirmationRequired` on ensure paths).
- **Reliability/infra (not a numbered subtask)** — de-flaked the Docker-backed
  integration suite (cross-worker course-creation lock #62; AJAX fallback on
  webservice context errors #64; post-boot login warmup #74; ephemeral CI
  containers + boot diagnostics #73) and fixed the Moodle 5.1 image boot
  (moosh `public/` dir, erseco/alpine-moodle#149).

**Partially done / next up:**

- **Phase B** — Subtask 34 (CLI help/option consistency), 35 (exit codes &
  batch summaries), 36 (shell completion).
- **Phase D** — Subtask 14 (ship `py.typed` now that the typed surface is
  real), 17–20 (extend the ensure-style API beyond `ensure_course`:
  `ensure_section`, `ensure_label`, `ensure_resource`, `ensure_folder`,
  `create_or_update_course`).
- **Phase E/F** — compatibility-flow audit, hybrid backend selection, and the
  module registration system remain largely greenfield.

### Phase A: Lock in the baseline and smooth contributor workflows

- **Subtask 1: Publish the technical baseline and roadmap plan.**
  - Deliverable: this document.
  - Why first: every later PR can reference shared assumptions instead of
    repeating the same audit.
- **Subtask 2: Keep CI coverage aligned with the declared support policy.**
  - This is effectively complete in CI today and should now be maintained rather
    than redesigned.
- **Subtask 3: Finish documenting the test layers.**
  - The unit vs. integration split is partially complete in the test layout and
    should be finished by documenting how to run each layer and by clearly
    identifying brittle HTML fixtures when they are introduced.
- **Subtask 25: Add HTML fixture regression coverage for fragile parsing.**
  - This gives later compatibility and logging changes a safer landing zone.
- **Subtask 10: Expand task-oriented documentation recipes.**
  - This can proceed in parallel with other foundation work once the baseline is
    published.

### Phase B: Improve CLI ergonomics before deeper refactors

- **Subtask 4: Add structured CLI output formats (`table`, `json`, `yaml`).**
  - This is a small, high-value improvement for automation users.
  - It also creates a stable output contract needed for later field filtering.
- **Subtask 5: Add field filtering for machine-readable output.**
  - Build directly on the structured output work.
- **Subtask 34: Improve CLI help text and option consistency.**
  - Best done after the output contract is settled so wording stays stable.
- **Subtask 35: Standardize exit codes and batch summaries.**
  - Build on the CLI help cleanup.
- **Subtask 36: Evaluate shell completion after the command surface is stable.**

### Phase C: Improve reliability and observability

- **Subtask 6: Improve exception wording and troubleshooting guidance.**
  - This is the safest first slice because it does not need architecture
    changes.
- **Subtask 7: Add a redacted debug mode for HTTP and parsing flows.**
  - Build on the exception and wording cleanup so messages stay consistent.
- **Subtask 8: Centralize timeout configuration.**
  - Introduce one config surface before adding retry behavior.
- **Subtask 9: Add safe retry support with backoff for read paths.**
  - Limit the first pass to idempotent operations and clearly document scope.

### Phase D: Improve API quality incrementally

- **Subtask 11: Write the typed model migration note.**
  - Decide the public boundary between `TypedDict`, dataclasses, and backward
    compatibility adapters.
- **Subtask 12: Introduce typed `Course` and `Section` models.**
  - These are the most central entities and touch both CLI and library usage.
- **Subtask 13: Add typed `User`, `Module`, and `UploadResult` models.**
- **Subtask 14: Ship `py.typed` only after the initial typed surface is real.**
- **Subtask 17: Design the ensure-style API semantics.**
- **Subtask 18: Implement `ensure_section`.**
- **Subtask 19: Implement `ensure_label` and `ensure_resource`.**
- **Subtask 20: Implement `ensure_folder` and `create_or_update_course`.**

### Phase E: Continue compatibility and backend hardening

- **Subtask 21: Keep the version-sensitive flow audit current.**
  - The compatibility layer already exists, so the next work should focus on
    documenting remaining fragile flows and filling test gaps.
- **Subtask 22: Keep version detection centralized during session initialization.**
  - This is already partially implemented and should be extended, not
    restarted.
- **Subtask 23: Document the compatibility-layer contribution model.**
- **Subtask 24: Migrate one additional fragile scraping flow at a time.**
- **Subtask 25: Expand HTML fixture-based regression tests alongside each migration.**
- **Subtask 26: Audit current webservice usage and backend candidates.**
- **Subtask 27: Design a hybrid backend selection strategy.**
- **Subtask 28: Implement one high-value operation with transparent backend
  fallback.**

### Phase F: Make extension and feature work cheaper

- **Subtask 29: Audit the current module/resource architecture with concrete
  extension pain points.**
- **Subtask 30: Design a minimal module registration system.**
- **Subtask 31: Migrate one or two existing modules through the new registration
  path.**
- **Subtask 32: Pick the next high-value feature slice only after the extension
  model is clearer.**
- **Subtask 33: Implement that single feature slice cleanly.**

### Phase G: Finish with low-risk polish

- **Subtask 15: Add dry-run support to the highest-risk mutating commands.**
- **Subtask 16: Add confirmations and `--yes` bypass for destructive
  operations.**
- **Subtask 37: Review packaging and tooling coherence.**
- **Subtask 38: Apply the minimal packaging/tooling cleanup plan.**

## Dependency-Aware Subtask Tree

The tree below groups the checklist into workstreams and shows the main blocking
relationships. Items marked as **already landed** or **partially landed** should
be extended instead of reimplemented.

- **Baseline and contributor workflow**
  - **1. Technical baseline audit** → foundation for 3, 4, 6, 8, 10, 15, 21, 26,
    29, 34, 37
  - **2. CI Python matrix** (**already landed**)
  - **3. Test layering** (**partially landed**) → supports 25
  - **10. Documentation recipes**
- **CLI ergonomics**
  - **4. Structured output** → **5. Field filtering**
  - **34. CLI help consistency** → **35. Exit codes and summaries**,
    **36. Shell completion**
- **Reliability and observability**
  - **6. Exception clarity** → **7. Debug mode**
  - **8. Configurable timeouts** → **9. Safe retry support**
- **Typed API and idempotent operations**
  - **11. Typed model migration note**
    - **12. Course and Section models**
      - **13. User, Module, UploadResult models**
        - **14. `py.typed` packaging**
  - **17. Ensure API design**
    - **18. `ensure_section`**
    - **19. `ensure_label` and `ensure_resource`**
    - **20. `ensure_folder` and `create_or_update_course`**
- **Compatibility and backend strategy**
  - **21. Moodle-version-sensitive audit** (**partially landed**)
    - **22. Version detection during session init** (**partially landed**)
      - **23. Compatibility-layer design** (**partially landed**)
        - **24. First migrated fragile flow** (**partially landed**)
    - **25. HTML fixture regression tests**
  - **26. Webservice usage audit**
    - **27. Backend selection strategy**
      - **28. First hybrid backend implementation**
- **Module architecture and feature expansion**
  - **29. Module/resource architecture audit**
    - **30. Plugin-friendly registration system**
      - **31. Migrate one or two existing modules**
  - **32. Select next feature slice**
    - **33. Implement selected capability**
- **Safety and polish**
  - **15. Dry-run support**
    - **16. Confirmation prompts and `--yes` bypass**
  - **34. CLI help consistency**
    - **35. Exit codes and summaries**
      - **36. Shell completion**
  - **37. Packaging/tooling coherence review**
    - **38. Packaging/tooling cleanup**
  - **10. Documentation recipes**

## Proposed Sequence of Small PRs

The PR sequence below favors narrow scope, clear validation, and reusable
foundations.

| PR | Scope | Why this order |
| --- | --- | --- |
| 1 | Publish the technical baseline and roadmap execution plan | Gives every later PR a shared reference point |
| 2 | Finish documenting test layers and contributor test commands | Small change, reduces onboarding friction immediately |
| 3 | Add HTML fixture scaffolding for brittle parsing tests | Strengthens safety before more compatibility work |
| 4 | Introduce `--output table|json|yaml` for a first command family | High-value UX improvement with contained surface area |
| 5 | Add `--fields` support for machine-readable output | Small follow-up once the output contract exists |
| 6 | Standardize user-visible exception messages and troubleshooting docs | Improves day-to-day usability without architecture churn |
| 7 | Add redacted debug tracing for HTTP/session flows | Builds on clearer errors and pays off during later refactors |
| 8 | Centralize timeout configuration | Small reliability improvement with broad leverage |
| 9 | Add safe retries with backoff for read-only operations | Depends on timeout config and should stay narrowly scoped |
| 10 | Publish the typed model migration note | Design-first step before touching public return values |
| 11 | Introduce typed `Course` and `Section` models | First incremental API improvement on central entities |
| 12 | Add `py.typed` packaging after the typed surface is credible | Keeps typing support honest and low-risk |
| 13 | Add dry-run to one mutating command family | Safety improvement with a small blast radius |
| 14 | Add confirmation prompts and `--yes` bypass for destructive commands | Natural follow-up to dry-run |
| 15 | Publish ensure-style API semantics and implement `ensure_section` | Smallest idempotent automation slice |
| 16 | Extend ensure support to labels/resources, then folders/courses | Builds on the same result semantics incrementally |
| 17 | Audit remaining version-sensitive flows and migrate one more fragile path | Reuses the compatibility layer already in the repo |
| 18 | Audit webservice usage, then implement one hybrid backend path | Good medium-sized architecture proof point |
| 19 | Audit module architecture and migrate one or two module handlers | Defers cost until lower-risk wins are complete |
| 20 | Pick and implement one new feature slice | Best done after the extension and compatibility story improves |
| 21 | Final CLI polish: help text, exit codes, completion | Keeps user-facing polish aligned with the final command surface |
| 22 | Packaging/tooling coherence cleanup | Low-risk cleanup after product-facing changes settle |
| 23 | Expand documentation recipes for the stabilized workflows | Best when new behavior is no longer moving quickly |

## Recommended Next PRs

If the roadmap is executed strictly for impact-per-line changed, the best next
small PRs are:

1. **Structured CLI output formats**
2. **Field filtering for machine-readable output**
3. **Exception clarity and troubleshooting**
4. **Centralized timeout configuration**
5. **Documentation recipes**

That order keeps the early work mergeable, user-visible, and low-risk while
setting up the more architectural phases for success.
