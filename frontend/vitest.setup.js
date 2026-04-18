/**
 * Vitest setup configuration for PR Tracker frontend tests.
 * Configures fast-check for property-based testing with minimum 100 iterations.
 */

import { configureGlobal } from 'fast-check';
import '@testing-library/jest-dom';

// Configure fast-check globally for all property tests
// Minimum 100 iterations as per design requirements
configureGlobal({
  numRuns: 100,           // Minimum 100 iterations for all property tests
  verbose: false,         // Set to true for debugging
  seed: undefined,        // Random seed (undefined = random)
  path: undefined,        // Replay path for reproducing failures
  endOnFailure: false,    // Continue running tests after first failure
});

// Export configuration for use in tests
export const propertyTestConfig = {
  numRuns: 100,
  verbose: false,
};

// Mock ResizeObserver for Recharts components
global.ResizeObserver = class ResizeObserver {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {
    // Mock implementation
  }
  unobserve() {
    // Mock implementation
  }
  disconnect() {
    // Mock implementation
  }
};
