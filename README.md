# PR Tracker

A web application to track and visualize GitHub pull request metrics over time.

## Features

- Track open PRs, unassigned PRs, and PRs older than 30 days
- Store historical snapshots in DuckDB database
- Visualize trends with interactive charts
- React frontend with Vite
- Flask backend for local development
- AWS Lambda support for serverless deployment
- Real-time progress tracking for historical imports

## Project Structure

```
.
├── track_open_prs.py                  # Main script to fetch and store PR data
├── import_historical_snapshots.py     # Import weekly snapshots for date ranges
├── backend/
│   ├── db/
│   │   └── schema.sql          # Database schema
│   ├── local/
│   │   └── server.py           # Local Flask API server
│   ├── lambda/
│   │   └── handler.py          # AWS Lambda handler
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx             # Main React component
    │   ├── main.jsx
    │   └── index.css
    ├── package.json
    ├── vite.config.js
    └── index.html
```

## Setup

### Backend (Local Development)

1. Install Python dependencies:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Initialize and start the local server:
```bash
cd local
python server.py
```

The API will be available at `http://localhost:5000`

### Frontend

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

### Import Historical Snapshots

To import weekly snapshots for a date range:

```bash
# Import from December 22, 2025 to today
python import_historical_snapshots.py 2025-12-22

# Import for a specific date range
python import_historical_snapshots.py 2025-12-22 2026-01-31
```

This will:
1. Generate weekly dates from start to end
2. For each date, fetch PRs that were open at that time
3. Store snapshots in the database
4. Skip dates that already have snapshots (prevents duplicates)

The script searches GitHub for PRs created before each target date and filters for those that were still open (not closed/merged yet) at that point in time.

### View the Dashboard

1. Make sure both backend and frontend servers are running
2. Open `http://localhost:5173` in your browser
3. View current stats, 30-day trends, and historical snapshots
4. Click on any snapshot to see the PRs from that point in time

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

- `GET /api/stats` - Get latest snapshot and 30-day trend
- `GET /api/snapshots?days=30` - Get snapshots from last N days
- `GET /api/snapshots/<id>/prs` - Get PRs for a specific snapshot
- `POST /api/snapshots` - Create a new snapshot

## Deployment (AWS Lambda)

The backend can be deployed as AWS Lambda functions with API Gateway. The SQLite database is stored in S3 and cached in `/tmp` for performance.

Required environment variables for Lambda:
- `DB_BUCKET` - S3 bucket name for database storage

## Development

### Database Schema

The database has three main tables:
- `pr_snapshots` - Stores summary metrics for each snapshot
- `prs` - Stores individual PR details linked to snapshots
- `pr_comments` - Stores comment counts per reviewer per PR

DuckDB is used instead of SQLite for better analytical query performance.

### Running Tests

Backend tests:
```bash
cd backend/local
python -m pytest test_server.py -v
# or
python test_server.py
```

Python script tests:
```bash
python -m pytest test_track_open_prs.py -v
# or
python test_track_open_prs.py
```

Frontend tests:
```bash
cd frontend
npm test
# or for UI mode
npm run test:ui
# or for coverage
npm run test:coverage
```

### Adding Features

- Backend: Modify `backend/local/server.py` for local dev, `backend/lambda/handler.py` for Lambda
- Frontend: Edit React components in `frontend/src/`
- Database: Update `backend/db/schema.sql` and reinitialize

## License

MIT
