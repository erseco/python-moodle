# Configuration

py-moodle uses environment variables for configuration, typically stored in a `.env` file.

## Setting Up Credentials

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file:** Replace `PROD` with the environment name you want to configure (`LOCAL`, `STAGING`, etc.).
   ```env
   # Production environment
   MOODLE_PROD_URL=https://sandbox.moodledemo.net

   # Your Moodle credentials
   MOODLE_PROD_USERNAME=admin
   MOODLE_PROD_PASSWORD=sandbox24

   # Optional: for SSO/CAS authentication
   # MOODLE_PROD_CAS_URL=https://cas.myuni.edu/cas
   # Optional: predefined webservice token (required for CAS)
   # MOODLE_PROD_WS_TOKEN=your_webservice_token
   ```

!!! danger "Security Warning"
    The `.env` file contains sensitive credentials. Never commit it to version control or share it publicly.

## Configuration Options

| Variable Pattern | Description | Required |
|------------------|-------------|----------|
| `MOODLE_<ENV>_URL` | Base URL of the `<ENV>` Moodle instance | ✅ Yes |
| `MOODLE_<ENV>_USERNAME` | Username for the `<ENV>` instance | ✅ Yes |
| `MOODLE_<ENV>_PASSWORD` | Password for the `<ENV>` instance | ✅ Yes |
| `MOODLE_<ENV>_CAS_URL` | CAS server URL for SSO | ❌ Optional |
| `MOODLE_<ENV>_WS_TOKEN` | Predefined webservice token (required for CAS) | ❌ Optional |

## Selecting the Environment

Choose which environment configuration to use with the `--env` option or by setting `MOODLE_ENV`.

```bash
MOODLE_ENV=prod py-moodle courses list
# or
py-moodle --env prod courses list
```

If omitted, the environment defaults to `local`.

## Testing Your Configuration

Verify your credentials work:

```bash
py-moodle courses list
```

If configured correctly, you should see a list of available courses.

## Troubleshooting

### Common Issues

**Invalid credentials error:**
- Double-check your username and password
- Ensure the `MOODLE_<ENV>_URL` is correct and accessible
- Try logging in through the web interface first

**SSL/TLS errors:**
- Some development instances use self-signed certificates
- For testing only, you might need to disable SSL verification

**CAS authentication not working:**
- Ensure `MOODLE_<ENV>_CAS_URL` points to your institution's CAS server
- Check that your credentials work through the CAS web interface
- Verify that `MOODLE_<ENV>_WS_TOKEN` is set when CAS is enabled
