import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import App from './App'

// Mock fetch
global.fetch = vi.fn()

describe('App Component', () => {
  beforeEach(() => {
    fetch.mockClear()
    // Provide default mock responses for tests that don't explicitly set them
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ latest: null, trend: [], reviewers: [] })
    })
  })

  it('renders the dashboard title', () => {
    render(<App />)
    expect(screen.getByText('PR Tracker Dashboard')).toBeInTheDocument()
  })

  it('renders import button', () => {
    render(<App />)
    expect(screen.getByText('Import New Data')).toBeInTheDocument()
  })

  it('fetches and displays stats on mount', async () => {
    const mockStats = {
      latest: {
        total_prs: 10,
        unassigned_count: 3,
        old_prs_count: 2
      },
      trend: [],
      reviewers: []
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockStats
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
    })
  })

  it('displays reviewer workload chart when data available', async () => {
    const mockStats = {
      latest: null,
      trend: [],
      reviewers: [
        { reviewer: 'user1', count: 5, comments: 10, approvals: 3 },
        { reviewer: 'user2', count: 3, comments: 7, approvals: 2 }
      ]
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockStats
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Current Reviewer Workload')).toBeInTheDocument()
    })
  })

  it('handles import button click', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ latest: null, trend: [], reviewers: [] })
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, message: 'Data imported successfully' })
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ latest: null, trend: [], reviewers: [] })
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    })

    render(<App />)

    const importButton = screen.getByText('Import New Data')
    fireEvent.click(importButton)

    await waitFor(() => {
      expect(screen.getByText('Importing...')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText('Data imported successfully!')).toBeInTheDocument()
    })
  })

  it('displays error message on import failure', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ latest: null, trend: [], reviewers: [] })
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: false, message: 'Import failed' })
    })

    render(<App />)

    const importButton = screen.getByText('Import New Data')
    fireEvent.click(importButton)

    await waitFor(() => {
      expect(screen.getByText('Import failed')).toBeInTheDocument()
    })
  })

  it('fetches PRs when snapshot is clicked', async () => {
    const mockSnapshots = [
      {
        id: 1,
        snapshot_date: '2024-01-01T00:00:00Z',
        repo_owner: 'test',
        repo_name: 'repo',
        total_prs: 5,
        unassigned_count: 1,
        old_prs_count: 0
      }
    ]

    const mockPRs = [
      {
        id: 1,
        pr_number: 123,
        title: 'Test PR',
        url: 'https://github.com/test/pr/123',
        age_days: 10,
        reviewers: 'user1 [APPROVED]'
      }
    ]

    const mockReviewers = [
      { reviewer: 'user1', count: 1, comments: 2, approvals: 1 }
    ]

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ latest: null, trend: [], reviewers: [] })
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSnapshots
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockPRs
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockReviewers
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/test\/repo/)).toBeInTheDocument()
    })

    const snapshotItem = screen.getByText(/test\/repo/)
    fireEvent.click(snapshotItem.closest('.pr-item'))

    await waitFor(() => {
      expect(screen.getByText('PRs in Snapshot')).toBeInTheDocument()
      expect(screen.getByText('Test PR')).toBeInTheDocument()
    })
  })

  it('displays tab navigation', () => {
    render(<App />)
    
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Compare Snapshots')).toBeInTheDocument()
    expect(screen.getByText('Historical Import')).toBeInTheDocument()
  })

  it('switches between tabs', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ latest: null, trend: [], reviewers: [] })
    })

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    })

    render(<App />)

    const compareTab = screen.getByText('Compare Snapshots')
    fireEvent.click(compareTab)

    await waitFor(() => {
      expect(screen.getByText('Select two snapshots to see what changed between them')).toBeInTheDocument()
    })
  })
})
