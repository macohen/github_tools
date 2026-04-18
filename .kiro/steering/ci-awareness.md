# CI/CD Awareness

## GitHub Actions

This project uses GitHub Actions for CI. The workflow is defined in `.github/workflows/test.yml`.

### Current CI Jobs

- **backend** — Runs `python -m pytest backend/local/test_server.py -v` with Python 3.12
- **frontend** — Runs `npx vitest --run` with Node.js 20 from the `frontend/` directory

### Rules

- When adding or removing test files, update `.github/workflows/test.yml` to match
- When adding new Python dependencies, ensure they are in `backend/requirements.txt` (CI installs from there)
- When adding new Node dependencies, ensure `frontend/package-lock.json` is committed (CI uses `npm ci`)
- If a new test suite is added (e.g., Electron tests), add a corresponding CI job
- Always verify tests pass locally before committing — CI runs the same commands
