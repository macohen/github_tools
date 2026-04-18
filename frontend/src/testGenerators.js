/**
 * Test data generators for property-based testing.
 * Provides fast-check arbitraries for generating PRs, snapshots, and reviewer strings.
 * 
 * Feature: pr-trend-enhancement
 */

import * as fc from 'fast-check';

// Reviewer status values
const REVIEWER_STATUSES = ['APPROVED', 'NO ACTION', 'CHANGES_REQUESTED', 'COMMENTED'];

/**
 * Generate a valid reviewer string in the format:
 * "username1 [STATUS], username2 [STATUS], ..."
 * 
 * @param {number} minReviewers - Minimum number of reviewers (default 0)
 * @param {number} maxReviewers - Maximum number of reviewers (default 5)
 * @returns {fc.Arbitrary<string|null>} Reviewer string or null/"None" for no reviewers
 * 
 * Examples:
 *   - null (no reviewers)
 *   - "None" (no reviewers)
 *   - "alice [APPROVED]"
 *   - "alice [APPROVED], bob [NO ACTION], charlie [APPROVED]"
 */
export const reviewerString = (minReviewers = 0, maxReviewers = 5) => {
  return fc.oneof(
    // No reviewers case
    fc.constantFrom(null, 'None'),
    // With reviewers case
    fc
      .array(
        fc.record({
          username: fc.stringMatching(/^[a-zA-Z0-9]{3,15}$/),
          status: fc.constantFrom(...REVIEWER_STATUSES),
        }),
        { minLength: Math.max(1, minReviewers), maxLength: maxReviewers }
      )
      .map((reviewers) =>
        reviewers.map((r) => `${r.username} [${r.status}]`).join(', ')
      )
  );
};

/**
 * Generate a PR record with realistic data.
 * 
 * @param {Object} options - Configuration options
 * @param {number} options.snapshotId - Optional fixed snapshot_id
 * @param {Date} options.fixedCreatedAt - Optional fixed created_at date
 * @returns {fc.Arbitrary<Object>} PR record with all required fields
 */
export const prRecord = ({ snapshotId, fixedCreatedAt } = {}) => {
  return fc.record({
    id: fc.integer({ min: 1, max: 1000000 }),
    snapshot_id: snapshotId !== undefined ? fc.constant(snapshotId) : fc.integer({ min: 1, max: 10000 }),
    pr_number: fc.integer({ min: 1, max: 10000 }),
    title: fc.string({ minLength: 10, maxLength: 100 }),
    url: fc.webUrl(),
    created_at: fixedCreatedAt !== undefined
      ? fc.constant(fixedCreatedAt.toISOString())
      : fc.date({ min: new Date(Date.now() - 180 * 24 * 60 * 60 * 1000), max: new Date() }).map(d => d.toISOString()),
    updated_at: fc.date({ min: new Date(Date.now() - 180 * 24 * 60 * 60 * 1000), max: new Date() }).map(d => d.toISOString()),
    age_days: fc.integer({ min: 0, max: 180 }),
    reviewers: reviewerString(),
    state: fc.constantFrom('open', 'closed'),
  });
};

/**
 * Generate a snapshot record with realistic data.
 * 
 * @param {Object} options - Configuration options
 * @param {Date} options.fixedDate - Optional fixed snapshot_date
 * @returns {fc.Arbitrary<Object>} Snapshot record with all required fields
 */
export const snapshotRecord = ({ fixedDate } = {}) => {
  return fc.record({
    id: fc.integer({ min: 1, max: 10000 }),
    snapshot_date: fixedDate !== undefined
      ? fc.constant(fixedDate.toISOString())
      : fc.date({ min: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), max: new Date() }).map(d => d.toISOString()),
    repo_owner: fc.stringMatching(/^[a-zA-Z0-9]{3,20}$/),
    repo_name: fc.stringMatching(/^[a-zA-Z0-9]{3,30}$/),
    total_prs: fc.integer({ min: 0, max: 100 }),
    unassigned_count: fc.integer({ min: 0, max: 50 }),
    old_prs_count: fc.integer({ min: 0, max: 50 }),
  });
};

/**
 * Generate a set of PRs for a specific snapshot.
 * 
 * @param {number} snapshotId - The snapshot ID these PRs belong to
 * @param {Date} snapshotDate - The snapshot date (PRs created_at should be <= this)
 * @param {number} minPrs - Minimum number of PRs (default 0)
 * @param {number} maxPrs - Maximum number of PRs (default 60)
 * @returns {fc.Arbitrary<Array>} Array of PR records
 */
export const prSetForSnapshot = (snapshotId, snapshotDate, minPrs = 0, maxPrs = 60) => {
  return fc.array(
    prRecord({
      snapshotId,
      fixedCreatedAt: fc.date({
        min: new Date(snapshotDate.getTime() - 180 * 24 * 60 * 60 * 1000),
        max: snapshotDate,
      }),
    }),
    { minLength: minPrs, maxLength: maxPrs }
  );
};

/**
 * Generate trend data array (array of snapshot metrics).
 * 
 * @param {number} days - Number of days of trend data (default 30)
 * @returns {fc.Arbitrary<Array>} Array of trend data points
 */
export const trendData = (days = 30) => {
  return fc.array(
    fc.record({
      snapshot_date: fc.date({ min: new Date(Date.now() - days * 24 * 60 * 60 * 1000), max: new Date() }).map(d => d.toISOString()),
      total_prs: fc.integer({ min: 0, max: 100 }),
      under_review_count: fc.integer({ min: 0, max: 100 }),
      two_approvals_count: fc.integer({ min: 0, max: 100 }),
      old_prs_count: fc.integer({ min: 0, max: 100 }),
    }),
    { minLength: 1, maxLength: days }
  );
};

// Convenience arbitraries for common use cases
export const reviewerStrings = reviewerString();
export const prRecords = prRecord();
export const snapshotRecords = snapshotRecord();

// Arbitraries for specific scenarios
export const reviewerWithApprovals = reviewerString(1, 5);
export const reviewerNoReviewers = fc.constantFrom(null, 'None');
export const openPrs = prRecord().filter((pr) => pr.state === 'open');
export const closedPrs = prRecord().filter((pr) => pr.state === 'closed');

// Threshold values
export const thresholdValues = fc.integer({ min: 1, max: 365 });
export const invalidThresholds = fc.oneof(
  fc.integer({ max: 0 }), // Zero or negative
  fc.constant(null),
  fc.constant(undefined),
  fc.constant('invalid'),
  fc.constant(NaN)
);
