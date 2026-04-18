# Security

## Secrets and Credentials

- Never hardcode tokens, API keys, passwords, or connection strings in code
- Use environment variables for all secrets (see `.env.example` for the pattern)
- Never commit `.env` files — they are in `.gitignore`
- When adding a new secret, add a placeholder to `.env.example`

## Input Validation

- Validate and sanitize all user input on API endpoints
- Use parameterized queries (`$1`, `$2`) for all SQL — never string interpolation with user data
- Validate numeric parameters (e.g., `threshold`, `snapshot_id`) are positive integers before use

## Dependencies

- Before committing dependency updates, check for known vulnerabilities:
  - Python: `pip-audit` (install with `pip install pip-audit`)
  - Python static analysis: `bandit` (install with `pip install bandit`)
  - Node: `npm audit`
- Do not ignore high-severity vulnerabilities — fix or document them
- Pin dependency versions in `backend/requirements.txt` (exact versions with `==`)
- Commit `package-lock.json` files for reproducible Node builds

## Pre-commit Hook

A pre-commit hook at `.githooks/pre-commit` runs automatically before each commit:
- `pip-audit` — checks Python deps for known CVEs (fails on any vulnerability)
- `bandit` — checks Python code for CWEs (fails on high severity only)
- `npm audit` — checks Node deps for known CVEs (fails on high severity only)

To enable: `git config core.hooksPath .githooks`

## Flask / Backend

- Never run Flask with `debug=True` in production
- CORS should be restricted to specific origins in production (currently allows all for local dev)
- The `/api/reset` endpoint drops all data — consider restricting access in non-local deployments
- Log errors but never expose stack traces to end users in production (only in debug mode)

## Electron

- `contextIsolation: true` and `nodeIntegration: false` must remain set in BrowserWindow
- Never load remote URLs in the main window — only localhost or file:// origins
- Validate IPC messages between main and renderer processes
