# Bugfix Requirements Document

## Introduction

The historical import feature incorrectly reports all records as duplicates even when the database contains no snapshots. This prevents users from importing any historical PR snapshot data. The bug occurs in the `check_snapshot_exists()` function in `import_historical_snapshots.py`, which uses a DATE() comparison that may incorrectly match snapshots when comparing dates.

The issue manifests when:
- User attempts to import historical snapshots for the first time (empty database)
- The import script reports all snapshots as "already exists, skipping"
- No data is actually imported into the database
- UI shows no snapshots despite the import claiming duplicates exist

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the database contains no snapshots AND the user runs historical import THEN the system incorrectly reports all snapshots as duplicates and skips importing them

1.2 WHEN `check_snapshot_exists()` executes the query `SELECT COUNT(*) FROM pr_snapshots WHERE DATE(snapshot_date) = DATE($1)` THEN the system may return incorrect results due to date comparison logic

1.3 WHEN snapshots are skipped as duplicates THEN the system does not verify that matching records actually exist in the database

### Expected Behavior (Correct)

2.1 WHEN the database contains no snapshots AND the user runs historical import THEN the system SHALL import all snapshots without reporting false duplicates

2.2 WHEN `check_snapshot_exists()` checks for existing snapshots THEN the system SHALL accurately determine whether a snapshot for the given date already exists in the database

2.3 WHEN the import process identifies a duplicate THEN the system SHALL verify that a matching snapshot record actually exists before skipping the import

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the database contains existing snapshots for specific dates AND the user attempts to re-import those same dates THEN the system SHALL CONTINUE TO correctly identify them as duplicates and skip re-importing

3.2 WHEN the import process successfully imports a new snapshot THEN the system SHALL CONTINUE TO store all PR data, comments, and metadata correctly in the database

3.3 WHEN the import process encounters actual errors (API failures, network issues) THEN the system SHALL CONTINUE TO report those errors accurately and increment the failure count
