# Implementation Plan

- [-] 1. Write bug condition exploration test
  - **Property 1: Fault Condition** - Empty Database Incorrectly Returns True
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases - empty database with various date strings
  - Test that check_snapshot_exists(date_str) returns False when pr_snapshots table is empty for all valid date strings in "YYYY-MM-DD" format
  - The test assertions should match the Expected Behavior: function returns False when no matching snapshot exists
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "check_snapshot_exists('2025-01-15') returns True on empty database instead of False")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1, 2.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Duplicates Still Detected
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: when snapshot exists for a date, check_snapshot_exists() returns True
  - Write property-based tests capturing observed behavior: for all dates where a snapshot exists in pr_snapshots, check_snapshot_exists(date_str) returns True
  - Property-based testing generates many test cases for stronger guarantees
  - Test cases: exact date match, different dates (should return False), multiple snapshots, timestamp precision
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1_

- [ ] 3. Fix for check_snapshot_exists() date comparison bug

  - [x] 3.1 Implement the fix
    - Replace DATE() comparison with explicit type casting approach
    - Change query to: `WHERE DATE(snapshot_date) = CAST(? AS DATE)`
    - This ensures the string parameter is properly cast to DATE type before comparison
    - Add debug logging to show the count returned by the query
    - Verify the fix handles empty database correctly (returns False)
    - _Bug_Condition: isBugCondition(input) where input.db_state.pr_snapshots.count == 0 AND check_snapshot_exists(input.date_str) == True_
    - _Expected_Behavior: check_snapshot_exists() returns False when no matching snapshot exists, True only when snapshot for that date actually exists_
    - _Preservation: When snapshot for specific date exists, function must continue to correctly identify it as duplicate and return True_
    - _Requirements: 2.1, 2.2, 3.1_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Empty Database Returns False
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Duplicates Still Detected
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
