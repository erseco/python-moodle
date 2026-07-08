# Troubleshooting

This guide covers the most common authentication, session, and test setup
problems when working with `python-moodle`.

## Authentication and Session Errors

### `Moodle login failed: invalid username or password`

- Verify `MOODLE_URL`, `MOODLE_USERNAME`, and `MOODLE_PASSWORD`.
- Confirm the Moodle site accepts direct login for that account.
- If the site uses CAS or another single sign-on flow, enable the matching CLI
  settings before retrying.

### `Authenticated to Moodle, but no webservice token or sesskey was available`

- Confirm the user can open the Moodle dashboard in a browser after logging in.
- Enable the Moodle mobile web service, or provide a pre-configured token when
  the site blocks automatic token creation.
- If the site uses CAS, confirm the session is returning to Moodle correctly
  after authentication.

### `Cannot call Moodle webservice ... without a webservice token`

- Use a user that can access the Moodle mobile web service.
- Provide a pre-configured token through configuration when the site does not
  allow token discovery.
- Prefer session-based helpers that accept a `sesskey` when a webservice token
  is not available.

### `Moodle login succeeded, but no sesskey was found on the dashboard`

- Open the Moodle dashboard manually and confirm it loads after login.
- Check whether the site immediately redirects back to the login page or an SSO
  prompt.
- Review reverse-proxy or CAS configuration if authenticated sessions are not
  preserved.

## Course Listing Errors

### `Listing courses requires a valid webservice token or sesskey`

- Re-authenticate so the session can refresh its `sesskey`.
- Use a Moodle account with permission to access the Moodle mobile web service
  if you need the REST listing path.

## Test Environment Issues

### Integration tests are skipped unexpectedly

Tests outside `tests/unit/` are marked as integration tests and are skipped
unless you pass `--integration`.

```bash
pytest --integration --moodle-env local -m integration -n auto
```

### Pytest exits before collection because configuration is incomplete

Add the required environment variables for the selected target to `.env`:

- `MOODLE_<ENV>_URL`
- `MOODLE_<ENV>_USERNAME`
- `MOODLE_<ENV>_PASSWORD`

For example, the local target uses `MOODLE_LOCAL_URL`,
`MOODLE_LOCAL_USERNAME`, and `MOODLE_LOCAL_PASSWORD`.

### The local Moodle host is unreachable

Start the local stack before retrying:

```bash
make upd
```

or:

```bash
docker compose up -d
```
