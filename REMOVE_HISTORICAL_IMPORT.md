# Remove Historical Import Feature

## Overview
Remove the historical import functionality from both backend and frontend to simplify the application.

## Backend Tasks

### Task 1: Remove Historical Import API Endpoint
**File**: `backend/local/server.py`

- [ ] Remove the `/api/import-historical` endpoint (lines ~560-690)
  - Delete the entire `import_historical()` function
  - Remove streaming progress logic
  - Remove subprocess execution for `import_historical_snapshots.py`

**Lines to remove**: ~130 lines starting from `@app.route("/api/import-historical", methods=["POST"])`

## Frontend Tasks

### Task 2: Remove Historical Import State Variables
**File**: `frontend/src/App.jsx`

- [ ] Remove state declarations (lines ~17-25):
  - `const [startDate, setStartDate] = useState('2025-12-22')`
  - `const [endDate, setEndDate] = useState('')`
  - `const [historicalImporting, setHistoricalImporting] = useState(false)`
  - `const [historicalMessage, setHistoricalMessage] = useState(null)`
  - `const [importProgress, setImportProgress] = useState(null)`
  - `const [currentWeek, setCurrentWeek] = useState(null)`
  - `const [progressPercent, setProgressPercent] = useState(0)`

### Task 3: Remove Historical Import Handler Function
**File**: `frontend/src/App.jsx`

- [ ] Remove `handleHistoricalImport` function (lines ~142-235)
  - Delete the entire async function
  - Remove API call to `/api/import-historical`
  - Remove streaming response handling logic

**Lines to remove**: ~90 lines

### Task 4: Remove Historical Import Tab Button
**File**: `frontend/src/App.jsx`

- [ ] Remove the "Historical Import" tab button (lines ~296-301)
  - Delete the button element with `activeTab === 'historical'` check
  - Keep only the "Dashboard" tab

**Lines to remove**: ~6 lines

### Task 5: Remove Historical Import UI Section
**File**: `frontend/src/App.jsx`

- [ ] Remove the entire historical import UI (lines ~513-590+)
  - Delete `{activeTab === 'historical' && (...)` section
  - Remove form with date inputs
  - Remove import button
  - Remove progress bar display
  - Remove progress summary display
  - Remove info box

**Lines to remove**: ~80+ lines

## Testing After Removal

- [ ] Verify backend starts without errors
- [ ] Verify frontend builds without errors
- [ ] Test that Dashboard tab still works correctly
- [ ] Test that "Import New Data" button still works
- [ ] Verify no console errors related to removed state variables

## Estimated Impact
- **Backend**: Remove ~130 lines (1 endpoint)
- **Frontend**: Remove ~180+ lines (7 state vars, 1 function, 1 tab, 1 UI section)
- **Total**: ~310+ lines removed

## Notes
- The `import_historical_snapshots.py` script file can remain in the repository for manual use if needed
- This change only removes the UI/API integration, not the underlying script
