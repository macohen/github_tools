# Requirements Document

## Introduction

This feature enhances the 30-day trend visualization in the PR Tracker application to provide more detailed metrics about pull request states over time. Currently, the trend shows only basic aggregated counts from snapshots. This enhancement will calculate metrics directly from PR data using actual PR dates, providing insights into PRs under review, PRs with two approvals, and configurable thresholds for identifying old PRs.

## Glossary

- **PR_Tracker**: The web application that tracks GitHub pull request metrics over time
- **Trend_API**: The backend REST API endpoint that provides trend data to the frontend
- **Frontend**: The React-based user interface that displays charts and metrics
- **PR_Database**: The DuckDB database containing pr_snapshots, prs, and pr_comments tables
- **Under_Review**: A PR state where at least one reviewer has been assigned
- **Approved_PR**: A PR that has received approval status from at least two reviewers
- **Old_PR_Threshold**: A configurable number of days used to identify PRs that have been open too long
- **Reviewer_Status**: The approval state of a reviewer, parsed from the reviewers field (e.g., [APPROVED], [NO ACTION])

## Requirements

### Requirement 1: Calculate PRs Under Review

**User Story:** As a team lead, I want to see how many PRs are under review over time, so that I can track review progress and identify bottlenecks.

#### Acceptance Criteria

1. WHEN the Trend_API calculates trend data, THE PR_Tracker SHALL count PRs with at least one assigned reviewer as "under review"
2. THE PR_Tracker SHALL parse the reviewers field from the prs table to determine if reviewers are assigned
3. THE PR_Tracker SHALL exclude PRs where reviewers field is NULL or "None" from the under review count
4. THE PR_Tracker SHALL include the under_review_count in the trend data response for each date

### Requirement 2: Calculate PRs with Two Approvals

**User Story:** As a team lead, I want to see how many PRs have received two approvals over time, so that I can understand how close PRs are to being merged.

#### Acceptance Criteria

1. WHEN the Trend_API calculates trend data, THE PR_Tracker SHALL parse the reviewers field to extract approval statuses
2. THE PR_Tracker SHALL count PRs where at least two reviewers have [APPROVED] status
3. THE PR_Tracker SHALL handle the reviewers field format "username [STATUS], username2 [STATUS]" correctly
4. THE PR_Tracker SHALL include the two_approvals_count in the trend data response for each date

### Requirement 3: Configurable Old PR Threshold

**User Story:** As a team lead, I want to configure what "old" means for PRs, so that I can adjust the threshold based on my team's workflow.

#### Acceptance Criteria

1. THE Trend_API SHALL accept an optional threshold parameter for old PR days
2. WHEN no threshold parameter is provided, THE Trend_API SHALL use 30 days as the default value
3. THE Trend_API SHALL calculate old_prs_count using the provided or default threshold
4. THE Frontend SHALL provide a user interface control to set the old PR threshold
5. WHEN the user changes the threshold, THE Frontend SHALL request updated trend data with the new threshold value

### Requirement 4: Date-Based Trend Calculation

**User Story:** As a team lead, I want trend data calculated from actual PR dates, so that I can see accurate historical states rather than just snapshot aggregates.

#### Acceptance Criteria

1. THE Trend_API SHALL calculate trend metrics from the prs table using created_at and updated_at timestamps
2. WHEN calculating metrics for a specific date, THE PR_Tracker SHALL include PRs where created_at is before or equal to that date AND state is "open"
3. THE PR_Tracker SHALL calculate age_days for each PR based on the difference between the trend date and the PR created_at date
4. THE PR_Tracker SHALL group trend data by snapshot_date from the pr_snapshots table
5. FOR ALL snapshots in the 30-day window, THE PR_Tracker SHALL recalculate metrics from associated PR records

### Requirement 5: Enhanced Trend API Response

**User Story:** As a frontend developer, I want the trend API to return all four metrics, so that I can display comprehensive trend charts.

#### Acceptance Criteria

1. THE Trend_API SHALL return trend data with the following fields for each date: snapshot_date, total_prs, under_review_count, two_approvals_count, old_prs_count
2. THE Trend_API SHALL maintain backward compatibility with existing total_prs field
3. THE Trend_API SHALL order trend data by snapshot_date in ascending order
4. WHEN the database contains no snapshots, THE Trend_API SHALL return an empty trend array

### Requirement 6: Frontend Trend Visualization

**User Story:** As a team lead, I want to see all four metrics visualized in the trend chart, so that I can quickly understand PR states over time.

#### Acceptance Criteria

1. THE Frontend SHALL display a line chart with four lines: total_prs, under_review_count, two_approvals_count, old_prs_count
2. THE Frontend SHALL use distinct colors for each metric line
3. THE Frontend SHALL include a legend identifying each metric
4. THE Frontend SHALL format dates on the X-axis as readable date strings
5. THE Frontend SHALL display metric values in tooltips when hovering over data points

### Requirement 7: Threshold Configuration UI

**User Story:** As a team lead, I want an easy way to adjust the old PR threshold, so that I can experiment with different values without technical knowledge.

#### Acceptance Criteria

1. THE Frontend SHALL provide an input control for setting the old PR threshold in days
2. THE Frontend SHALL display the current threshold value (default 30)
3. WHEN the user changes the threshold value, THE Frontend SHALL validate that it is a positive integer
4. WHEN the user submits a new threshold, THE Frontend SHALL fetch updated trend data with the new threshold parameter
5. THE Frontend SHALL display the threshold value used in the current chart

### Requirement 8: Performance for Historical Data

**User Story:** As a system administrator, I want trend calculations to perform efficiently, so that users don't experience slow page loads.

#### Acceptance Criteria

1. THE Trend_API SHALL use database indexes on snapshot_date and snapshot_id for efficient queries
2. THE Trend_API SHALL limit trend calculations to the requested time window (default 30 days)
3. WHEN calculating metrics for multiple dates, THE Trend_API SHALL use efficient SQL queries with JOINs rather than multiple round trips
4. THE Trend_API SHALL complete trend calculation requests within 2 seconds for 30 days of data
