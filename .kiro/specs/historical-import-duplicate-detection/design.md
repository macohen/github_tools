# Historical Import Duplicate Detection Bugfix Design

## Overview

The `check_snapshot_exists()` function in `import_historical_snapshots.py` incorrectly reports that snapshots already exist even when the database is empty. This prevents any historical data from being imported on first run. The bug stems from the DATE() comparison logic in the SQL query, which may be incorrectly evaluating the date comparison or handling the parameterized query incorrectly. The fix will ensure accurate duplicate detection by using a more reliable date comparison approach while preserving the existing duplicate detection functionality for actual duplicates.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when the database is empty (no snapshots exist) but `check_snapshot_exists()` returns True
- **Property (P)**: The desired behavior - `check_snapshot_exists()` should return False when no matching snapshot exists, and True only when a snapshot for that date actually exists
- **Preservation**: Existing duplicate detection behavior that correctly identifies and skips re-importing snapshots that already exist in the database
- **check_snapshot_exists()**: The function in `import_historical_snapshots.py` (line 34) that queries the database to determine if a snapshot for a given date already exists
- **snapshot_date**: The TIMESTAMP column in the pr_snapshots table that stores when each snapshot was taken
- **date_str**: The input parameter in "YYYY-MM-DD" format representing the date to check for existing snapshots

## Bug Details

### Fault Condition

The bug manifests when the database contains no snapshots (empty pr_snapshots table) and the user runs the historical import script. The `check_snapshot_exists()` function incorrectly returns True, causing the import process to skip all snapshots with the message "already exists, skipping". The root cause is likely in how the DATE() function comparison handles the parameterized query or how DuckDB evaluates `DATE(snapshot_date) = DATE($1)` when comparing TIMESTAMP values to string date parameters.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type { date_str: string, db_state: DatabaseState }
  OUTPUT: boolean
  
  RETURN input.db_state.pr_snapshots.count == 0
         AND check_snapshot_exists(input.date_str) == True
         AND input.date_str matches format "YYYY-MM-DD"
END FUNCTION
```

### Examples

- **Example 1**: Database is empty, user runs `python import_historical_snapshots.py 2025-01-01`
  - Expected: Import proceeds, snapshots are created
  - Actual: All snapshots skipped with "already exists" message, no data imported

- **Example 2**: Database is empty, check_snapshot_exists("2025-01-15") is called
  - Expected: Returns False (no snapshot exists for this date)
  - Actual: Returns True (incorrectly reports snapshot exists)

- **Example 3**: Database has snapshot for 2025-01-01, user attempts to re-import 2025-01-01
  - Expected: Returns True, skips import (correct duplicate detection)
  - Actual: Should continue to work correctly after fix

- **Edge Case**: Database has snapshots for 2025-01-01 and 2025-01-15, user imports 2025-01-08
  - Expected: Returns False (no snapshot for 2025-01-08), proceeds with import

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- When a snapshot for a specific date already exists in the database, the function must continue to correctly identify it as a duplicate and return True
- The import process must continue to skip re-importing snapshots that genuinely exist
- All snapshot data storage functionality (store_snapshot, process_prs) must remain unchanged
- Error handling for API failures, network issues, and database connection problems must remain unchanged

**Scope:**
All inputs where a matching snapshot actually exists in the database should be completely unaffected by this fix. This includes:
- Re-running imports for dates that have already been imported
- Running imports that overlap with existing snapshot dates
- Any scenario where legitimate duplicate detection should occur

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **DATE() Function Behavior**: DuckDB's DATE() function may not be correctly parsing the string parameter `$1` when it's in "YYYY-MM-DD" format, potentially causing the comparison to always evaluate to true or to match incorrectly

2. **Parameterized Query Handling**: The parameterized query with `DATE($1)` may not be binding the parameter correctly, causing the WHERE clause to behave unexpectedly

3. **Type Mismatch**: Comparing DATE(snapshot_date) (which extracts date from TIMESTAMP) with DATE($1) (which parses a string) may have implicit type conversion issues in DuckDB

4. **Query Logic Error**: The COUNT(*) with WHERE clause might be returning incorrect results due to how DuckDB evaluates the date comparison when the table is empty or when date formats don't match exactly

## Correctness Properties

Property 1: Fault Condition - Empty Database Returns False

_For any_ date string in "YYYY-MM-DD" format where the pr_snapshots table contains no records, the fixed check_snapshot_exists function SHALL return False, indicating that no snapshot exists for that date.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Existing Duplicates Still Detected

_For any_ date string where a snapshot record already exists in the pr_snapshots table with a matching snapshot_date (same calendar day), the fixed check_snapshot_exists function SHALL return True, preserving the existing duplicate detection behavior.

**Validates: Requirements 3.1**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `import_historical_snapshots.py`

**Function**: `check_snapshot_exists` (line 34)

**Specific Changes**:
1. **Replace DATE() Comparison**: Change the query to use a more explicit date comparison that doesn't rely on DATE() function behavior
   - Option A: Cast the string parameter to DATE explicitly: `WHERE DATE(snapshot_date) = CAST($1 AS DATE)`
   - Option B: Use date range comparison: `WHERE snapshot_date >= $1 AND snapshot_date < ($1::DATE + INTERVAL 1 DAY)`
   - Option C: Format both sides consistently: `WHERE DATE_TRUNC('day', snapshot_date) = DATE_TRUNC('day', CAST($1 AS DATE))`

2. **Add Explicit Type Casting**: Ensure the parameter is properly cast to a DATE type before comparison to avoid implicit conversion issues

3. **Improve Error Handling**: Consider whether returning False on exception is appropriate, or if exceptions should propagate to indicate a real problem

4. **Add Debug Logging**: Add a debug log statement showing the count returned by the query to help diagnose issues in the future

5. **Verify Table Existence**: Optionally add a check to ensure the pr_snapshots table exists before querying it, though CREATE TABLE IF NOT EXISTS should handle this

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Fault Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that create an empty database, call check_snapshot_exists() with various date strings, and assert that it returns False. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Empty Database Test**: Create empty pr_snapshots table, call check_snapshot_exists("2025-01-15") (will fail on unfixed code - should return False but returns True)
2. **Multiple Dates Test**: Test multiple different dates on empty database (will fail on unfixed code)
3. **Date Format Variations**: Test with different valid date formats to see if format affects the bug (may fail on unfixed code)
4. **Table Non-Existence Test**: Test behavior when pr_snapshots table doesn't exist at all (may fail on unfixed code)

**Expected Counterexamples**:
- check_snapshot_exists() returns True when database is empty (should return False)
- Possible causes: DATE() comparison always evaluating to true, parameterized query not binding correctly, type conversion issue

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL date_str WHERE database_is_empty() DO
  result := check_snapshot_exists_fixed(date_str)
  ASSERT result == False
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL date_str WHERE snapshot_exists_for_date(date_str) DO
  ASSERT check_snapshot_exists_original(date_str) == True
  ASSERT check_snapshot_exists_fixed(date_str) == True
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for scenarios where snapshots actually exist, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Exact Date Match Preservation**: Insert snapshot for 2025-01-15, verify check_snapshot_exists("2025-01-15") returns True on both unfixed and fixed code
2. **Different Date No Match**: Insert snapshot for 2025-01-15, verify check_snapshot_exists("2025-01-20") returns False on both versions
3. **Multiple Snapshots**: Insert snapshots for multiple dates, verify each date is correctly detected as existing
4. **Timestamp Precision**: Insert snapshot with specific timestamp (e.g., 2025-01-15 14:30:00), verify date-only check still matches

### Unit Tests

- Test check_snapshot_exists() with empty database returns False
- Test check_snapshot_exists() with existing snapshot for exact date returns True
- Test check_snapshot_exists() with existing snapshot for different date returns False
- Test edge cases: leap years, month boundaries, year boundaries
- Test error handling when database connection fails

### Property-Based Tests

- Generate random dates in valid format, verify empty database always returns False
- Generate random dates and insert matching snapshots, verify function always returns True for those dates
- Generate random dates with existing snapshots for other dates, verify function returns False for non-matching dates
- Test across many date scenarios to ensure date comparison logic is robust

### Integration Tests

- Test full import flow with empty database, verify all snapshots are imported
- Test full import flow with some existing snapshots, verify only new ones are imported
- Test re-running import for same date range, verify all are correctly skipped as duplicates
- Test that imported data is correctly stored and queryable after fix
