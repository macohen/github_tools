/**
 * Verification tests for test data generators.
 * Ensures generators produce valid data for property-based testing.
 * 
 * Feature: pr-trend-enhancement
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import {
  reviewerString,
  prRecord,
  snapshotRecord,
  trendData,
  thresholdValues,
  invalidThresholds,
} from './testGenerators';

describe('Test Data Generators', () => {
  it('should generate valid reviewer strings', () => {
    fc.assert(
      fc.property(reviewerString(), (reviewers) => {
        if (reviewers === null || reviewers === 'None') {
          // No reviewers case
          return true;
        }
        
        // Has reviewers - should be comma-separated with statuses
        expect(typeof reviewers).toBe('string');
        expect(reviewers.length).toBeGreaterThan(0);
        
        // Check format: "username [STATUS], username2 [STATUS]"
        const reviewerEntries = reviewers.split(', ');
        for (const entry of reviewerEntries) {
          expect(entry).toContain('[');
          expect(entry).toContain(']');
        }
        
        return true;
      })
    );
  });

  it('should generate valid PR records', () => {
    fc.assert(
      fc.property(prRecord(), (pr) => {
        // Check required fields exist
        expect(pr).toHaveProperty('id');
        expect(pr).toHaveProperty('snapshot_id');
        expect(pr).toHaveProperty('pr_number');
        expect(pr).toHaveProperty('title');
        expect(pr).toHaveProperty('url');
        expect(pr).toHaveProperty('created_at');
        expect(pr).toHaveProperty('updated_at');
        expect(pr).toHaveProperty('age_days');
        expect(pr).toHaveProperty('reviewers');
        expect(pr).toHaveProperty('state');
        
        // Check field types and constraints
        expect(typeof pr.id).toBe('number');
        expect(pr.id).toBeGreaterThan(0);
        expect(typeof pr.snapshot_id).toBe('number');
        expect(pr.snapshot_id).toBeGreaterThan(0);
        expect(typeof pr.pr_number).toBe('number');
        expect(pr.pr_number).toBeGreaterThan(0);
        expect(typeof pr.title).toBe('string');
        expect(pr.title.length).toBeGreaterThanOrEqual(10);
        expect(typeof pr.url).toBe('string');
        expect(typeof pr.created_at).toBe('string');
        expect(typeof pr.updated_at).toBe('string');
        expect(typeof pr.age_days).toBe('number');
        expect(pr.age_days).toBeGreaterThanOrEqual(0);
        expect(['open', 'closed']).toContain(pr.state);
        
        return true;
      })
    );
  });

  it('should generate valid snapshot records', () => {
    fc.assert(
      fc.property(snapshotRecord(), (snapshot) => {
        // Check required fields exist
        expect(snapshot).toHaveProperty('id');
        expect(snapshot).toHaveProperty('snapshot_date');
        expect(snapshot).toHaveProperty('repo_owner');
        expect(snapshot).toHaveProperty('repo_name');
        expect(snapshot).toHaveProperty('total_prs');
        expect(snapshot).toHaveProperty('unassigned_count');
        expect(snapshot).toHaveProperty('old_prs_count');
        
        // Check field types and constraints
        expect(typeof snapshot.id).toBe('number');
        expect(snapshot.id).toBeGreaterThan(0);
        expect(typeof snapshot.snapshot_date).toBe('string');
        expect(typeof snapshot.repo_owner).toBe('string');
        expect(snapshot.repo_owner.length).toBeGreaterThanOrEqual(3);
        expect(typeof snapshot.repo_name).toBe('string');
        expect(snapshot.repo_name.length).toBeGreaterThanOrEqual(3);
        expect(typeof snapshot.total_prs).toBe('number');
        expect(snapshot.total_prs).toBeGreaterThanOrEqual(0);
        expect(typeof snapshot.unassigned_count).toBe('number');
        expect(snapshot.unassigned_count).toBeGreaterThanOrEqual(0);
        expect(typeof snapshot.old_prs_count).toBe('number');
        expect(snapshot.old_prs_count).toBeGreaterThanOrEqual(0);
        
        return true;
      })
    );
  });

  it('should generate valid trend data arrays', () => {
    fc.assert(
      fc.property(trendData(30), (trend) => {
        // Check it's an array
        expect(Array.isArray(trend)).toBe(true);
        expect(trend.length).toBeGreaterThanOrEqual(1);
        expect(trend.length).toBeLessThanOrEqual(30);
        
        // Check each entry has required fields
        for (const entry of trend) {
          expect(entry).toHaveProperty('snapshot_date');
          expect(entry).toHaveProperty('total_prs');
          expect(entry).toHaveProperty('under_review_count');
          expect(entry).toHaveProperty('two_approvals_count');
          expect(entry).toHaveProperty('old_prs_count');
          
          expect(typeof entry.snapshot_date).toBe('string');
          expect(typeof entry.total_prs).toBe('number');
          expect(entry.total_prs).toBeGreaterThanOrEqual(0);
          expect(typeof entry.under_review_count).toBe('number');
          expect(entry.under_review_count).toBeGreaterThanOrEqual(0);
          expect(typeof entry.two_approvals_count).toBe('number');
          expect(entry.two_approvals_count).toBeGreaterThanOrEqual(0);
          expect(typeof entry.old_prs_count).toBe('number');
          expect(entry.old_prs_count).toBeGreaterThanOrEqual(0);
        }
        
        return true;
      })
    );
  });

  it('should generate valid threshold values', () => {
    fc.assert(
      fc.property(thresholdValues, (threshold) => {
        expect(typeof threshold).toBe('number');
        expect(threshold).toBeGreaterThanOrEqual(1);
        expect(threshold).toBeLessThanOrEqual(365);
        return true;
      })
    );
  });

  it('should generate invalid threshold values for testing validation', () => {
    fc.assert(
      fc.property(invalidThresholds, (threshold) => {
        // Should be one of: negative, zero, null, undefined, string, NaN
        const isInvalid =
          threshold === null ||
          threshold === undefined ||
          typeof threshold === 'string' ||
          Number.isNaN(threshold) ||
          (typeof threshold === 'number' && threshold <= 0);
        
        expect(isInvalid).toBe(true);
        return true;
      })
    );
  });
});
