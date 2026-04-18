# PR Tracker

A web and desktop application to track and visualize GitHub pull request metrics over time.

## Features

- Track open PRs, unassigned PRs, and PRs older than 30 days
- Traffic light indicators (🟢🟡🔴) based on approval status
- Compare snapshots to see what changed between two points in time
- Auto-loads the most recent snapshot on startup
- Store snapshots in DuckDB with automatic checkpoint on shutdown
- Visualize trends with interactive charts
- Reviewer workload breakdown with comments and approvals
- Deep linking URLs for sharing specific views
- Approval status filters (All, Ready, Partial, Needs Review)
- React frontend with Vite
- Flask backend with REST API
- Electron desktop app with bundled backend and persistent database

## Project Structure

```
.
├── track_open_prs.py                  # Main script to fetch and store PR data
├── backend/
│   ├── db/
│   │   └── schema.sql                # Database schema
│   ├── local/
│   │   ├── server.py                 # Flask API server
│   │   ├── test_server.py            # Backend tests
│   │   └── test_server_properties.py # Property-based tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                   # Main React component
│   │   ├── App.test.jsx              # Frontend tests
│   │   ├── api.js                    # API fetch helper (web + Electron)
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── electron/
│   ├── main.js                       # Electron main process
│   ├── preload.js                    # Context bridge for renderer
│   └── package.json                  # Electron + electron-builder config
└── docs/
    └── slack-app-best-practices.md   # Reference docs
```

## Security

### Environment Variables

This application requires sensitive credentials that should never be committed to git:

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your credentials:**
   - `GITHUB_TOKEN` - Create a personal access token at https://github.com/settings/tokens
     - For public repos: `public_repo` scope
     - For private repos: `repo` scope
   - Never commit your `.env` file (it's already in `.gitignore`)

3. **Load environment variables:**
   ```bash
   # Option 1: Export manually
   export GITHUB_TOKEN="your_token_here"
   
   # Option 2: Use a tool like direnv or python-dotenv
   source .env
   ```

### Security Best Practices

- ✅ Use read-only GitHub tokens when possible
- ✅ Rotate tokens regularly
- ✅ Never commit tokens or `.env` files to git
- ✅ Use environment-specific tokens (dev vs prod)
- ⚠️ In production, disable Flask debug mode
- ⚠️ In production, restrict CORS to specific origins
- ⚠️ Use HTTPS in production deployments

## Setup

### Option 1: Web App (Development)

#### Backend

1. Install Python dependencies:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set up environment variables (see Security section above)

3. Start the local server:
```bash
cd local
python server.py
```

The API will be available at `http://localhost:5001`

#### Frontend

1. Install Node dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Option 2: Electron Desktop App

The Electron app bundles both the frontend and backend into a single distributable application. The Flask server runs as a child process inside the app.

#### Development Mode

```bash
cd electron
npm install
npm run dev
```

In dev mode, Electron will check if the Vite dev server is running on `localhost:5173`. If it is, it uses that (with hot reload). If not, it falls back to the pre-built frontend in `electron/frontend-dist/`. The Flask backend is spawned using the project's `backend/.venv/bin/python3`.

To rebuild the frontend for Electron after making changes:
```bash
cd frontend
npx vite build --mode electron
```

#### Building for Distribution

Prerequisites:
- Node.js and npm
- Python 3.12+ with PyInstaller (`pip install pyinstaller`)

```bash
cd electron

# Build everything (frontend + backend + package)
npm run build

# Or build steps individually:
npm run build:frontend    # Vite builds React app into electron/frontend-dist/
npm run build:backend     # PyInstaller bundles Flask into a single executable
npm run dist              # electron-builder packages the app
```

The packaged app will be in `electron/release/`.

#### How It Works

1. Electron's main process finds an available port (starting at 5001)
2. Spawns the Flask backend as a child process (PyInstaller binary in production, venv Python in dev)
3. Waits for the backend to respond to health checks
4. Injects `window.__BACKEND_PORT__` into the HTML so the frontend knows where to send API calls
5. Loads the React frontend in a BrowserWindow
6. On startup, the most recent snapshot is automatically loaded and displayed
7. On quit, DuckDB is checkpointed (`CHECKPOINT` command) to flush all data to disk

#### Database Persistence

The database (`pr_tracker.duckdb`) is stored in the OS user data directory and persists across app restarts:
- macOS: `~/Library/Application Support/Pull Request Tracker Dashboard/`
- Linux: `~/.config/Pull Request Tracker Dashboard/`
- Windows: `%APPDATA%/Pull Request Tracker Dashboard/`

To start fresh, use `File → Reset Database...` from the menu bar. This deletes the database file, restarts the backend, and reloads the frontend with a clean state.

## Usage

### Collect and Store PR Data

Set up environment variables:
```bash
export GITHUB_TOKEN="your-github-token"
export GITHUB_REPO="awslabs/aws-athena-query-federation"
```

Run the script to store a snapshot:
```bash
python track_open_prs.py --store
```

This will:
1. Fetch all open PRs from GitHub
2. Get reviewer information for each PR
3. Store the snapshot in the database via the API

### View the Dashboard

1. Make sure both backend and frontend servers are running (or use the Electron app)
2. Open `http://localhost:5173` in your browser
3. The most recent snapshot loads automatically on startup
4. Click on any snapshot to see the PRs from that point in time
5. Use approval filters (🟢🟡🔴) to focus on PRs by review status
6. Use the Compare Snapshots tab to diff two snapshots

### Publish to Quip

To publish a report to Quip instead of storing:
```bash
export QUIP_TOKEN="your-quip-token"
python track_open_prs.py
```

To update an existing Quip doc:
```bash
export QUIP_DOC_ID="doc-id"
python track_open_prs.py
```

### Automation

Set up a cron job to collect data regularly:
```bash
# Run every 6 hours
0 */6 * * * cd /path/to/pr-tracker && /path/to/.venv/bin/python track_open_prs.py --store
```

## API Endpoints

- `GET /api/stats` - Get latest snapshot, 30-day trend, and reviewer workload
- `GET /api/stats?threshold=14` - Custom age threshold for "old PRs" metric
- `GET /api/snapshots?days=30` - Get snapshots from last N days
- `GET /api/snapshots/<id>/prs` - Get PRs for a specific snapshot
- `GET /api/snapshots/<id>/reviewers` - Get reviewer workload for a snapshot
- `GET /api/snapshots/compare?snapshot1=X&snapshot2=Y` - Compare two snapshots
- `POST /api/snapshots` - Create a new snapshot
- `DELETE /api/snapshots/<id>` - Delete a snapshot and its associated data
- `POST /api/import` - Trigger a live data import

## Development

### Database Schema

The database has three main tables:
- `pr_snapshots` - Stores summary metrics for each snapshot
- `prs` - Stores individual PR details linked to snapshots
- `pr_comments` - Stores comment counts per reviewer per PR

DuckDB is used instead of SQLite for better analytical query performance. The schema uses `CREATE IF NOT EXISTS` so it is safe to run on an existing database.

### Running Tests

Backend tests (22 tests):
```bash
cd backend/local
python -m pytest test_server.py -v
```

Frontend tests (20 tests):
```bash
cd frontend
npm test
# or for UI mode
npm run test:ui
# or for coverage
npm run test:coverage
```

### Backend Configuration

The Flask server supports these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `pr_tracker.duckdb` | Path to the DuckDB database file |
| `FLASK_PORT` | `5001` | Port for the Flask server |
| `FLASK_DEBUG` | `1` | Enable/disable debug mode (`1`/`0`) |
| `SCHEMA_PATH` | `../db/schema.sql` | Path to the database schema file |
| `RUNNING_IN_ELECTRON` | (unset) | When set, disables Flask's auto-reloader |

### Adding Features

- Backend: Modify `backend/local/server.py`
- Frontend: Edit React components in `frontend/src/`
- Database: Update `backend/db/schema.sql` and reinitialize
- Electron: Modify `electron/main.js` for main process changes

## License

Apache-2.0
