import { useState, useEffect, useRef } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { apiFetch } from './api'

// Parse hash params from URL
function getHashParams() {
  const hash = window.location.hash.slice(1) // remove '#'
  const params = new URLSearchParams(hash)
  return {
    tab: params.get('tab') || 'dashboard',
    snapshot: params.get('snapshot') ? Number(params.get('snapshot')) : null,
    filter: params.get('filter') || 'all',
    cmp1: params.get('cmp1') ? Number(params.get('cmp1')) : null,
    cmp2: params.get('cmp2') ? Number(params.get('cmp2')) : null,
  }
}

// Build hash string from state
function buildHash(params) {
  const p = new URLSearchParams()
  if (params.tab && params.tab !== 'dashboard') p.set('tab', params.tab)
  if (params.snapshot) p.set('snapshot', params.snapshot)
  if (params.filter && params.filter !== 'all') p.set('filter', params.filter)
  if (params.cmp1) p.set('cmp1', params.cmp1)
  if (params.cmp2) p.set('cmp2', params.cmp2)
  const str = p.toString()
  return str ? `#${str}` : ''
}

function App() {
  const initialParams = getHashParams()
  const [activeTab, setActiveTab] = useState(initialParams.tab)
  const [stats, setStats] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [selectedSnapshot, setSelectedSnapshot] = useState(initialParams.snapshot)
  const [selectedSnapshotReviewers, setSelectedSnapshotReviewers] = useState(null)
  const [prs, setPrs] = useState([])
  const [importing, setImporting] = useState(false)
  const [importMessage, setImportMessage] = useState(null)
  const [deletingSnapshot, setDeletingSnapshot] = useState(null)
  const [approvalFilter, setApprovalFilter] = useState(initialParams.filter)
  
  // Comparison state
  const [compareSnapshot1, setCompareSnapshot1] = useState(initialParams.cmp1)
  const [compareSnapshot2, setCompareSnapshot2] = useState(initialParams.cmp2)
  const [comparisonResult, setComparisonResult] = useState(null)
  const [comparing, setComparing] = useState(false)
  
  // Track whether we're handling a popstate to avoid circular updates
  const isPopState = useRef(false)

  // Update URL hash when linkable state changes
  useEffect(() => {
    if (isPopState.current) {
      isPopState.current = false
      return
    }
    const newHash = buildHash({
      tab: activeTab,
      snapshot: selectedSnapshot,
      filter: approvalFilter,
      cmp1: compareSnapshot1,
      cmp2: compareSnapshot2,
    })
    if (window.location.hash !== newHash) {
      window.history.pushState(null, '', newHash || window.location.pathname)
    }
  }, [activeTab, selectedSnapshot, approvalFilter, compareSnapshot1, compareSnapshot2])

  // Handle browser back/forward
  useEffect(() => {
    const onPopState = () => {
      isPopState.current = true
      const params = getHashParams()
      setActiveTab(params.tab)
      setSelectedSnapshot(params.snapshot)
      setApprovalFilter(params.filter)
      setCompareSnapshot1(params.cmp1)
      setCompareSnapshot2(params.cmp2)
      // Load snapshot data if navigating back to one
      if (params.snapshot) {
        fetchPRs(params.snapshot)
      }
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  // On initial load, if URL has a snapshot, load its data
  useEffect(() => {
    fetchStats()
    fetchSnapshots().then(loadedSnapshots => {
      if (initialParams.snapshot) {
        fetchPRs(initialParams.snapshot)
      } else if (loadedSnapshots && loadedSnapshots.length > 0) {
        // Auto-load the most recent snapshot
        fetchPRs(loadedSnapshots[0].id)
      }
    })
  }, [])

  const fetchStats = async () => {
    try {
      const res = await apiFetch('/api/stats')
      const data = await res.json()
      
      if (res.ok) {
        setStats(data)
      } else {
        // Handle error response
        console.error('Failed to fetch stats:', data)
        // Could set an error state here if needed
      }
    } catch (error) {
      console.error('Error fetching stats:', error)
    }
  }

  const fetchSnapshots = async () => {
    try {
      const res = await apiFetch('/api/snapshots?days=30')
      const data = await res.json()
      
      if (res.ok) {
        setSnapshots(data)
        return data
      } else {
        // Handle error response
        console.error('Failed to fetch snapshots:', data)
        return []
      }
    } catch (error) {
      console.error('Error fetching snapshots:', error)
      return []
    }
  }

  const fetchPRs = async (snapshotId) => {
    try {
      const res = await apiFetch(`/api/snapshots/${snapshotId}/prs`)
      const data = await res.json()
      
      if (res.ok) {
        setPrs(data)
        setSelectedSnapshot(snapshotId)
        
        // Also fetch reviewer stats for this snapshot
        const reviewerRes = await apiFetch(`/api/snapshots/${snapshotId}/reviewers`)
        const reviewerData = await reviewerRes.json()
        
        if (reviewerRes.ok) {
          setSelectedSnapshotReviewers(reviewerData)
        } else {
          console.error('Failed to fetch reviewer stats:', reviewerData)
          setSelectedSnapshotReviewers(null)
        }
      } else {
        // Handle error response
        console.error('Failed to fetch PRs:', data)
        setPrs([])
        setSelectedSnapshotReviewers(null)
      }
    } catch (error) {
      console.error('Error fetching PRs:', error)
      setPrs([])
      setSelectedSnapshotReviewers(null)
    }
  }

  const handleImport = async () => {
    setImporting(true)
    setImportMessage(null)
    
    try {
      const res = await apiFetch('/api/import', { method: 'POST' })
      const data = await res.json()
      
      if (data.success) {
        setImportMessage({ type: 'success', text: 'Data imported successfully!' })
        // Refresh data and auto-load the newest snapshot
        await fetchStats()
        const loadedSnapshots = await fetchSnapshots()
        if (loadedSnapshots && loadedSnapshots.length > 0) {
          fetchPRs(loadedSnapshots[0].id)
        }
      } else {
        // Build detailed error message
        let errorText = data.message || 'Import failed'
        
        // Add stderr if available
        if (data.error) {
          errorText += '\n\nError output:\n' + data.error
        }
        
        // Add stdout if available
        if (data.stdout) {
          errorText += '\n\nScript output:\n' + data.stdout
        }
        
        // Add debug info if available
        if (data.debug) {
          errorText += '\n\nDebug info:\n' + JSON.stringify(data.debug, null, 2)
        }
        
        // Add traceback if available
        if (data.traceback) {
          errorText += '\n\nStack trace:\n' + data.traceback
        }
        
        setImportMessage({ type: 'error', text: errorText })
      }
    } catch (error) {
      setImportMessage({ type: 'error', text: `Import error: ${error.message}` })
    } finally {
      setImporting(false)
    }
  }

  const handleDeleteSnapshot = async (snapshotId, event) => {
    event.stopPropagation() // Prevent triggering the snapshot click
    
    if (!confirm('Are you sure you want to delete this snapshot? This will also delete all associated PRs and comments.')) {
      return
    }
    
    setDeletingSnapshot(snapshotId)
    
    try {
      const res = await apiFetch(`/api/snapshots/${snapshotId}`, { method: 'DELETE' })
      const data = await res.json()
      
      if (res.ok) {
        // Refresh snapshots list and stats
        await fetchSnapshots()
        await fetchStats()
        
        // Clear selected snapshot if it was deleted
        if (selectedSnapshot === snapshotId) {
          setSelectedSnapshot(null)
          setPrs([])
          setSelectedSnapshotReviewers(null)
        }
      } else {
        // Build detailed error message
        let errorText = data.message || 'Failed to delete snapshot'
        
        if (data.error) {
          errorText += '\n\nError: ' + data.error
        }
        
        if (data.traceback) {
          errorText += '\n\nStack trace:\n' + data.traceback
        }
        
        alert(errorText)
      }
    } catch (error) {
      alert(`Error deleting snapshot: ${error.message}`)
    } finally {
      setDeletingSnapshot(null)
    }
  }

  const handleCompareSnapshots = async () => {
    if (!compareSnapshot1 || !compareSnapshot2) {
      alert('Please select two snapshots to compare')
      return
    }
    
    if (compareSnapshot1 === compareSnapshot2) {
      alert('Please select two different snapshots')
      return
    }
    
    setComparing(true)
    setComparisonResult(null)
    
    try {
      const res = await apiFetch(`/api/snapshots/compare?snapshot1=${compareSnapshot1}&snapshot2=${compareSnapshot2}`)
      const data = await res.json()
      
      if (res.ok) {
        setComparisonResult(data)
      } else {
        alert(`Comparison failed: ${data.message || 'Unknown error'}`)
      }
    } catch (error) {
      alert(`Error comparing snapshots: ${error.message}`)
    } finally {
      setComparing(false)
    }
  }

  return (
    <div className="container">
      <div className="header">
        <h1>PR Tracker Dashboard</h1>
      </div>

      <div className="tabs">
        <button 
          className={`tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          Dashboard
        </button>
        <button 
          className={`tab ${activeTab === 'compare' ? 'active' : ''}`}
          onClick={() => setActiveTab('compare')}
        >
          Compare Snapshots
        </button>
      </div>

      {activeTab === 'dashboard' && (
        <>
          <div className="action-bar">
            <button 
              onClick={handleImport} 
              disabled={importing}
              className="import-button"
            >
              {importing ? 'Importing...' : 'Import New Data'}
            </button>
            {importMessage && (
              <div className={`message ${importMessage.type}`}>
                {importMessage.text}
              </div>
            )}
          </div>

          {stats?.latest && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.latest.total_prs}</div>
                <div className="stat-label">Total Open PRs</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.latest.unassigned_count}</div>
                <div className="stat-label">No Reviewers</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.latest.old_prs_count}</div>
                <div className="stat-label">Open &gt;30 Days</div>
              </div>
            </div>
          )}


          {stats?.reviewers && stats.reviewers.length > 0 && (
            <div className="chart-container">
              <h2>Current Reviewer Workload</h2>
              <p style={{ color: '#666', marginBottom: '15px' }}>
                {selectedSnapshotReviewers 
                  ? `Showing data for selected snapshot (ID: ${selectedSnapshot})`
                  : 'Showing data from latest snapshot'}
              </p>
              <ResponsiveContainer width="100%" height={Math.max(500, (selectedSnapshotReviewers || stats.reviewers).length * 60)}>
                <BarChart 
                  data={selectedSnapshotReviewers || stats.reviewers} 
                  layout="vertical" 
                  margin={{ left: 20, top: 20, bottom: 20 }}
                  barCategoryGap="20%"
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis 
                    dataKey="reviewer" 
                    type="category" 
                    width={150}
                    interval={0}
                    tick={{ fontSize: 13 }}
                  />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" fill="#0066cc" name="PRs Assigned" />
                  <Bar dataKey="comments" fill="#ffa500" name="Comments Made" />
                  <Bar dataKey="approvals" fill="#28a745" name="Approvals Given" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="chart-container">
            <h2>Recent Snapshots</h2>
            {snapshots.map(snapshot => (
              <div 
                key={snapshot.id} 
                className="pr-item snapshot-item"
                onClick={() => fetchPRs(snapshot.id)}
              >
                <div className="snapshot-content">
                  <div>
                    <div className="pr-title">
                      {new Date(snapshot.snapshot_date).toLocaleString()} - {snapshot.repo_owner}/{snapshot.repo_name}
                    </div>
                    <div className="pr-meta">
                      {snapshot.total_prs} PRs | {snapshot.unassigned_count} unassigned | {snapshot.old_prs_count} old
                    </div>
                  </div>
                  <button
                    className="delete-button"
                    onClick={(e) => handleDeleteSnapshot(snapshot.id, e)}
                    disabled={deletingSnapshot === snapshot.id}
                    title="Delete snapshot"
                  >
                    {deletingSnapshot === snapshot.id ? 'Deleting...' : '×'}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {selectedSnapshot && prs.length > 0 && (
            <div className="pr-list">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '15px' }}>
                <h2 style={{ margin: 0 }}>PRs in Snapshot</h2>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => setApprovalFilter('all')}
                    style={{
                      padding: '6px 12px',
                      fontSize: '14px',
                      backgroundColor: approvalFilter === 'all' ? '#0066cc' : '#f0f0f0',
                      color: approvalFilter === 'all' ? 'white' : '#333',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    All
                  </button>
                  <button
                    onClick={() => setApprovalFilter('green')}
                    style={{
                      padding: '6px 12px',
                      fontSize: '14px',
                      backgroundColor: approvalFilter === 'green' ? '#28a745' : '#f0f0f0',
                      color: approvalFilter === 'green' ? 'white' : '#333',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    🟢 Ready
                  </button>
                  <button
                    onClick={() => setApprovalFilter('yellow')}
                    style={{
                      padding: '6px 12px',
                      fontSize: '14px',
                      backgroundColor: approvalFilter === 'yellow' ? '#ffa500' : '#f0f0f0',
                      color: approvalFilter === 'yellow' ? 'white' : '#333',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    🟡 Partial
                  </button>
                  <button
                    onClick={() => setApprovalFilter('red')}
                    style={{
                      padding: '6px 12px',
                      fontSize: '14px',
                      backgroundColor: approvalFilter === 'red' ? '#dc3545' : '#f0f0f0',
                      color: approvalFilter === 'red' ? 'white' : '#333',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    🔴 Needs Review
                  </button>
                </div>
              </div>
              {prs
                .filter(pr => {
                  // Apply approval filter
                  if (approvalFilter === 'all') return true;
                  
                  const approvalCount = pr.reviewers 
                    ? (pr.reviewers.match(/\[APPROVED\]/g) || []).length 
                    : 0;
                  
                  if (approvalFilter === 'green') return approvalCount >= 2;
                  if (approvalFilter === 'yellow') return approvalCount === 1;
                  if (approvalFilter === 'red') return approvalCount === 0;
                  
                  return true;
                })
                .map(pr => {
                // Count approvals
                const approvalCount = pr.reviewers 
                  ? (pr.reviewers.match(/\[APPROVED\]/g) || []).length 
                  : 0;
                
                // Determine traffic light color
                let trafficLight = '🔴'; // Red - no approvals
                if (approvalCount >= 2) {
                  trafficLight = '🟢'; // Green - ready to merge
                } else if (approvalCount === 1) {
                  trafficLight = '🟡'; // Yellow - one approval
                }
                
                return (
                  <div key={pr.id} className="pr-item">
                    <div className="pr-title">
                      <span style={{ marginRight: '8px', fontSize: '18px' }}>{trafficLight}</span>
                      <a href={pr.url} target="_blank" rel="noopener noreferrer">
                        {pr.title}
                      </a>
                    </div>
                    <div className="pr-meta">
                      Age: {pr.age_days} days | Reviewers: {pr.reviewers || 'None'}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {activeTab === 'compare' && (
        <div className="comparison-view">
          <h2>Compare Snapshots</h2>
          <p style={{ color: '#666', marginBottom: '20px' }}>
            Select two snapshots to see what changed between them
          </p>

          <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
                Snapshot 1 (Earlier)
              </label>
              <select
                value={compareSnapshot1 || ''}
                onChange={(e) => setCompareSnapshot1(Number(e.target.value))}
                style={{ width: '100%', padding: '8px', fontSize: '14px' }}
              >
                <option value="">Select snapshot...</option>
                {snapshots.map(snapshot => (
                  <option key={snapshot.id} value={snapshot.id}>
                    {new Date(snapshot.snapshot_date).toLocaleString()} - {snapshot.repo_owner}/{snapshot.repo_name}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
                Snapshot 2 (Later)
              </label>
              <select
                value={compareSnapshot2 || ''}
                onChange={(e) => setCompareSnapshot2(Number(e.target.value))}
                style={{ width: '100%', padding: '8px', fontSize: '14px' }}
              >
                <option value="">Select snapshot...</option>
                {snapshots.map(snapshot => (
                  <option key={snapshot.id} value={snapshot.id}>
                    {new Date(snapshot.snapshot_date).toLocaleString()} - {snapshot.repo_owner}/{snapshot.repo_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleCompareSnapshots}
            disabled={comparing || !compareSnapshot1 || !compareSnapshot2}
            className="import-button"
            style={{ marginBottom: '20px' }}
          >
            {comparing ? 'Comparing...' : 'Compare Snapshots'}
          </button>

          {comparisonResult && (
            <div>
              <div className="stats-grid" style={{ marginBottom: '30px' }}>
                <div className="stat-card">
                  <div className="stat-value">{comparisonResult.summary.new_count}</div>
                  <div className="stat-label">New PRs</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{comparisonResult.summary.closed_count}</div>
                  <div className="stat-label">Closed PRs</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{comparisonResult.summary.status_changed_count}</div>
                  <div className="stat-label">Status Changed</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{comparisonResult.summary.unchanged_count}</div>
                  <div className="stat-label">Unchanged</div>
                </div>
              </div>

              {comparisonResult.new_prs.length > 0 && (
                <div className="pr-list" style={{ marginBottom: '30px' }}>
                  <h3>🆕 New PRs ({comparisonResult.new_prs.length})</h3>
                  {comparisonResult.new_prs.map(pr => (
                    <div key={pr.pr_number} className="pr-item">
                      <div className="pr-title">
                        <span style={{ marginRight: '8px', fontSize: '18px' }}>
                          {pr.color === 'green' ? '🟢' : pr.color === 'yellow' ? '🟡' : '🔴'}
                        </span>
                        <a href={pr.url} target="_blank" rel="noopener noreferrer">
                          {pr.title}
                        </a>
                      </div>
                      <div className="pr-meta">
                        Age: {pr.age_days} days | Reviewers: {pr.reviewers || 'None'}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {comparisonResult.status_changed.length > 0 && (
                <div className="pr-list" style={{ marginBottom: '30px' }}>
                  <h3>🔄 Status Changed ({comparisonResult.status_changed.length})</h3>
                  {comparisonResult.status_changed.map(pr => (
                    <div key={pr.pr_number} className="pr-item">
                      <div className="pr-title">
                        <span style={{ marginRight: '8px', fontSize: '18px' }}>
                          {pr.color_before === 'green' ? '🟢' : pr.color_before === 'yellow' ? '🟡' : '🔴'}
                          →
                          {pr.color_after === 'green' ? '🟢' : pr.color_after === 'yellow' ? '🟡' : '🔴'}
                        </span>
                        <a href={pr.url} target="_blank" rel="noopener noreferrer">
                          {pr.title}
                        </a>
                      </div>
                      <div className="pr-meta">
                        Age: {pr.age_days} days | Approvals: {pr.approval_count_before} → {pr.approval_count_after} | Reviewers: {pr.reviewers || 'None'}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {comparisonResult.closed_prs.length > 0 && (
                <div className="pr-list" style={{ marginBottom: '30px' }}>
                  <h3>✅ Closed PRs ({comparisonResult.closed_prs.length})</h3>
                  {comparisonResult.closed_prs.map(pr => (
                    <div key={pr.pr_number} className="pr-item">
                      <div className="pr-title">
                        <span style={{ marginRight: '8px', fontSize: '18px' }}>
                          {pr.color === 'green' ? '🟢' : pr.color === 'yellow' ? '🟡' : '🔴'}
                        </span>
                        <a href={pr.url} target="_blank" rel="noopener noreferrer">
                          {pr.title}
                        </a>
                      </div>
                      <div className="pr-meta">
                        Age: {pr.age_days} days | Reviewers: {pr.reviewers || 'None'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

    </div>
  )
}

export default App
