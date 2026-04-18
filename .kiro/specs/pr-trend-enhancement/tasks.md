# Implementation Plan: PR Trend Enhancement

## Overview

This implementation plan adds four detailed metrics to the 30-day PR trend visualization: total PRs, PRs under review, PRs with two approvals, and old PRs (with configurable threshold). The implementation modifies the backend `/api/stats` endpoint to calculate metrics using SQL queries, adds a threshold parameter, and enhances the frontend with a 4-line chart and threshold configuration UI.

## Tasks

- [x] 1. Set up testing framework and property-based test infrastructure
  - Install hypothesis library for Python backend property tests
  - Install fast-check library for JavaScript frontend property tests
  - Configure test runners to execute property tests with minimum 100 iterations
  - Create test data generators for PRs, snapshots, and reviewer strings
  - _Requirements: All (testing foundation)_

- [x] 2. Implement backend SQL-based metric calculation
  - [x] 2.1 Modify `/api/stats` endpoint to accept threshold parameter
    - Add optional `threshold` query parameter (integer, default=30)
    - Add input validation for threshold (must be positive integer)
    - Return 400 Bad Request for invalid threshold values
    - _Requirements: 3.1, 3.2_
  
  - [x]* 2.2 Write property test for threshold validation
    - **Property 9: Threshold Input Validation**
    - **Validates: Requirements 7.3**
    - Generate random inputs (negative, zero, non-numeric, valid)
    - Verify validation accepts only positive integers
  
  - [x] 2.3 Implement SQL query for calculating all four metrics
    - Create CTE for snapshot_dates within requested time window
    - Create CTE for pr_metrics with aggregated counts
    - Calculate under_review_count using reviewers field check
    - Calculate two_approvals_count by counting [APPROVED] occurrences in reviewers field
    - Calculate old_prs_count using age_days > threshold comparison
    - Use LEFT JOIN to handle snapshots with no PRs
    - Order results by snapshot_date ascending
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.3, 4.1, 4.2, 4.3, 4.4, 5.3, 8.2, 8.3_
  
  - [x]* 2.4 Write property test for under review count accuracy
    - **Property 1: Under Review Count Accuracy**
    - **Validates: Requirements 1.1, 1.2**
    - Generate random sets of PRs with various reviewer field values
    - Verify under_review_count equals PRs where reviewers is not NULL and not "None"
  
  - [x]* 2.5 Write property test for reviewer string parsing
    - **Property 2: Reviewer String Parsing**
    - **Validates: Requirements 2.1, 2.3**
    - Generate random valid reviewer strings with varying numbers of reviewers
    - Verify parser extracts all entries without errors
  
  - [x]* 2.6 Write property test for two approvals count accuracy
    - **Property 3: Two Approvals Count Accuracy**
    - **Validates: Requirements 2.2**
    - Generate random sets of PRs with 0-5 approvals each
    - Verify two_approvals_count matches PRs with >= 2 approvals
  
  - [x]* 2.7 Write property test for threshold-based old PR calculation
    - **Property 4: Threshold-Based Old PR Calculation**
    - **Validates: Requirements 3.3**
    - Generate random threshold values (1-365) and random PR ages (0-500 days)
    - Verify old_prs_count matches PRs where age > threshold
  
  - [x]* 2.8 Write property test for PR filtering by date and state
    - **Property 5: PR Filtering by Date and State**
    - **Validates: Requirements 4.2**
    - Generate random PRs with various created_at dates and states
    - Verify only open PRs created before snapshot date are included
  
  - [x]* 2.9 Write property test for age calculation consistency
    - **Property 6: Age Calculation Consistency**
    - **Validates: Requirements 4.3**
    - Generate random PR created_at dates and snapshot dates
    - Verify age_days equals date difference in days

- [x] 3. Update API response structure with new metrics
  - [x] 3.1 Add new fields to trend array response
    - Add under_review_count field to each trend entry
    - Add two_approvals_count field to each trend entry
    - Maintain existing total_prs and old_prs_count fields for backward compatibility
    - Ensure all fields default to 0 for snapshots with no PRs
    - _Requirements: 1.4, 2.4, 5.1, 5.2_
  
  - [x]* 3.2 Write property test for trend data ordering
    - **Property 7: Trend Data Ordering**
    - **Validates: Requirements 5.3**
    - Generate random snapshots with unsorted dates
    - Verify API returns them in ascending chronological order
  
  - [x]* 3.3 Write property test for time window filtering
    - **Property 8: Time Window Filtering**
    - **Validates: Requirements 8.2**
    - Generate random time windows (1-90 days)
    - Verify results only include snapshots within window
  
  - [x]* 3.4 Write unit tests for API response structure
    - Test response includes all required fields
    - Test backward compatibility with existing consumers
    - Test empty database returns empty trend array
    - Test error handling for database connection failures
    - _Requirements: 5.1, 5.2, 5.4_

- [x] 4. Checkpoint - Ensure backend tests pass
  - Run all backend unit tests and property tests
  - Verify API endpoint returns correct data structure
  - Test with sample database containing realistic data
  - Ensure all tests pass, ask the user if questions arise

- [ ] 5. Implement frontend threshold configuration UI
  - [ ] 5.1 Create threshold input component
    - Add number input field for threshold value
    - Set default value to 30 days
    - Add label "Old PR Threshold (days):"
    - Add validation for positive integers only
    - Display current threshold value in use
    - _Requirements: 7.1, 7.2, 7.5_
  
  - [ ]* 5.2 Write property test for threshold change triggers refresh
    - **Property 10: Threshold Change Triggers Refresh**
    - **Validates: Requirements 3.5, 7.4**
    - Generate random valid threshold changes
    - Verify each triggers API call with correct parameter
  
  - [ ] 5.3 Implement threshold change handler
    - Validate user input is positive integer
    - Show validation error for invalid inputs
    - Debounce API calls (500ms delay after user stops typing)
    - Call `/api/stats` with new threshold parameter
    - Update chart with new data
    - _Requirements: 3.5, 7.3, 7.4_
  
  - [ ]* 5.4 Write unit tests for threshold input component
    - Test component renders with default value
    - Test validation rejects zero and negative numbers
    - Test validation rejects non-numeric input
    - Test onChange handler is called with valid input
    - _Requirements: 7.1, 7.2, 7.3_

- [ ] 6. Implement enhanced trend chart visualization
  - [ ] 6.1 Update chart component to display four metric lines
    - Add Line component for total_prs (blue #0066cc)
    - Add Line component for under_review_count (green #28a745)
    - Add Line component for two_approvals_count (purple #6f42c1)
    - Add Line component for old_prs_count (orange #ffa500)
    - Configure all lines with type="monotone"
    - _Requirements: 6.1, 6.2_
  
  - [ ] 6.2 Configure chart legend and tooltips
    - Add Legend component with descriptive names for each metric
    - Configure Tooltip to show metric values on hover
    - Format tooltip labels as readable date strings
    - _Requirements: 6.3, 6.5_
  
  - [ ] 6.3 Format X-axis dates for readability
    - Use tickFormatter to convert dates to locale date strings
    - Ensure dates are displayed in ascending order
    - _Requirements: 6.4_
  
  - [ ]* 6.4 Write property test for date formatting consistency
    - **Property 11: Date Formatting Consistency**
    - **Validates: Requirements 6.4**
    - Generate random dates
    - Verify formatted strings are valid and human-readable
  
  - [ ]* 6.5 Write unit tests for chart component
    - Test chart renders with four lines
    - Test each line has correct color
    - Test legend displays all metric names
    - Test tooltip appears on hover
    - Test X-axis displays formatted dates
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 7. Implement error handling and edge cases
  - [ ] 7.1 Add backend error handling
    - Handle invalid threshold parameter (return 400 Bad Request)
    - Handle database connection failures (return 500 Internal Server Error)
    - Handle malformed reviewers field (log warning, treat as no reviewers)
    - Handle query timeouts (return 504 Gateway Timeout)
    - Log all errors with context for debugging
    - _Requirements: 8.1, 8.3_
  
  - [ ] 7.2 Add frontend error handling
    - Display error message for API request failures
    - Provide "Retry" button for failed requests
    - Show "No data available" message for empty responses
    - Implement error boundary for chart rendering failures
    - Show inline validation errors for threshold input
    - _Requirements: 7.3_
  
  - [ ]* 7.3 Write unit tests for error scenarios
    - Test backend returns 400 for invalid threshold
    - Test backend returns 500 for database errors
    - Test frontend displays error message on API failure
    - Test frontend shows validation error for invalid threshold
    - Test frontend displays "No data available" for empty data

- [ ] 8. Integration and wiring
  - [ ] 8.1 Wire threshold input to API calls
    - Connect threshold input component to stats fetching logic
    - Pass threshold parameter to `/api/stats` endpoint
    - Update chart when new data is received
    - _Requirements: 3.5, 7.4_
  
  - [ ] 8.2 Verify backward compatibility
    - Test existing API consumers still work without threshold parameter
    - Verify default threshold (30 days) is used when parameter is omitted
    - Ensure existing total_prs field is still present in response
    - _Requirements: 5.2_
  
  - [ ]* 8.3 Write integration tests for end-to-end flows
    - Test user loads dashboard and sees 4-line chart with default threshold
    - Test user changes threshold and chart updates
    - Test empty database displays "No data available"
    - Test API error displays error message with retry button
    - _Requirements: All_

- [ ] 9. Performance validation and optimization
  - [ ] 9.1 Verify query performance meets requirements
    - Test trend calculation for 30 days completes in < 2 seconds
    - Test trend calculation for 90 days completes in < 5 seconds
    - Verify single SQL query is used (no N+1 queries)
    - Check database indexes on snapshot_date and snapshot_id exist
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  
  - [ ]* 9.2 Run performance benchmarks
    - Benchmark with 1000+ snapshots and 50,000+ PRs
    - Test with 10 concurrent users requesting trend data
    - Verify frontend chart renders in < 500ms
    - Verify threshold change response in < 1 second

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Run all backend unit tests and property tests
  - Run all frontend unit tests and property tests
  - Run integration tests for end-to-end scenarios
  - Verify performance benchmarks meet requirements
  - Test with realistic data (90 days, 20-60 PRs per snapshot)
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use hypothesis (Python) and fast-check (JavaScript) libraries
- All property tests run with minimum 100 iterations
- Backend uses SQL-based calculations for efficiency
- Frontend uses Recharts library for visualization
- API maintains backward compatibility with existing consumers
