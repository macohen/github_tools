import { useState, useEffect } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [stats, setStats] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const [prs, setPrs] = useState([])
  const [importing, setImporting] = useState(false)
  const [importMessage, setImportMessage] = useState(null)
  const [deletingSnapshot, setDeletingSnapshot] = useState(null)
  
  // Historical import state
  const [startDate, setStartDate] = useState('2025-12-22')
  const [endDate, setEndDate] = useState('')
  const [historicalImporting, setHistoricalImporting] = useState(false)
  const [historicalMessage, setHistoricalMessage] = useState(null)
  const [importProgress, setImportProgress] = useState(null)
  const [currentWeek, setCurrentWeek] = useState(null)
  const [progressPercent, setProgressPercent] = useState(0)

  useEffect(() => {
    fetchStats()
    fetchSnapshots()
  }, [])

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/stats')
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
      const res = await fetch('/api/snapshots?days=30')
      const data = await res.json()
      
      if (res.ok) {
        setSnapshots(data)
      } else {
        // Handle error response
        console.error('Failed to fetch snapshots:', data)
      }
    } catch (error) {
      console.error('Error fetching snapshots:', error)
    }
  }

  const fetchPRs = async (snapshotId) => {
    try {
      const res = await fetch(`/api/snapshots/${snapshotId}/prs`)
      const data = await res.json()
      
      if (res.ok) {
        setPrs(data)
        setSelectedSnapshot(snapshotId)
      } else {
        // Handle error response
        console.error('Failed to fetch PRs:', data)
        setPrs([])
      }
    } catch (error) {
      console.error('Error fetching PRs:', error)
      setPrs([])
    }
  }

  const handleImport = async () => {
    setImporting(true)
    setImportMessage(null)
    
    try {
      const res = await fetch('/api/import', { method: 'POST' })
      const data = await res.json()
      
      if (data.success) {
        setImportMessage({ type: 'success', text: 'Data imported successfully!' })
        // Refresh data
        await fetchStats()
        await fetchSnapshots()
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

  const handleHistoricalImport = async () => {
    if (!startDate) {
      setHistoricalMessage({ type: 'error', text: 'Start date is required' })
      return
    }

    setHistoricalImporting(true)
    setHistoricalMessage(null)
    setImportProgress(null)
    setCurrentWeek(null)
    setProgressPercent(0)

    try {
      const params = new URLSearchParams({ start_date: startDate })
      if (endDate) {
        params.append('end_date', endDate)
      }

      const response = await fetch(`/api/import-historical?${params}`, { method: 'POST' })
      
      // Check if response is streaming
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('text/event-stream')) {
        // Handle streaming response
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6))
              
              if (data.type === 'progress') {
                setCurrentWeek(data.current_date)
                setProgressPercent(data.percent)
              } else if (data.type === 'complete') {
                setImportProgress(data)
                setHistoricalMessage({
                  type: 'success',
                  text: `Successfully imported ${data.imported} snapshots, skipped ${data.skipped} duplicates`
                })
                // Refresh data
                await fetchStats()
                await fetchSnapshots()
              } else if (data.type === 'error') {
                // Build detailed error message
                let errorText = data.message
                
                // Add debug info if available
                if (data.debug) {
                  errorText += '\n\nDebug info:\n' + JSON.stringify(data.debug, null, 2)
                }
                
                // Add traceback if available
                if (data.traceback) {
                  errorText += '\n\nStack trace:\n' + data.traceback
                }
                
                setHistoricalMessage({ type: 'error', text: errorText })
              }
            }
          }
        }
      } else {
        // Fallback to non-streaming response
        const data = await response.json()
        
        if (data.success) {
          setHistoricalMessage({ 
            type: 'success', 
            text: `Successfully imported ${data.imported} snapshots, skipped ${data.skipped} duplicates` 
          })
          setImportProgress(data)
          await fetchStats()
          await fetchSnapshots()
        } else {
          setHistoricalMessage({ type: 'error', text: data.message || 'Import failed' })
        }
      }
    } catch (error) {
      setHistoricalMessage({ type: 'error', text: `Import error: ${error.message}` })
    } finally {
      setHistoricalImporting(false)
      setCurrentWeek(null)
    }
  }

  const handleDeleteSnapshot = async (snapshotId, event) => {
    event.stopPropagation() // Prevent triggering the snapshot click
    
    if (!confirm('Are you sure you want to delete this snapshot? This will also delete all associated PRs and comments.')) {
      return
    }
    
    setDeletingSnapshot(snapshotId)
    
    try {
      const res = await fetch(`/api/snapshots/${snapshotId}`, { method: 'DELETE' })
      const data = await res.json()
      
      if (res.ok) {
        // Refresh snapshots list and stats
        await fetchSnapshots()
        await fetchStats()
        
        // Clear selected snapshot if it was deleted
        if (selectedSnapshot === snapshotId) {
          setSelectedSnapshot(null)
          setPrs([])
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
          className={`tab ${activeTab === 'historical' ? 'active' : ''}`}
          onClick={() => setActiveTab('historical')}
        >
          Historical Import
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

          {stats?.trend && stats.trend.length > 0 && (
            <div className="chart-container">
              <h2>30-Day Trend</h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={stats.trend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="snapshot_date" 
                    tickFormatter={(date) => new Date(date).toLocaleDateString()}
                  />
                  <YAxis />
                  <Tooltip labelFormatter={(date) => new Date(date).toLocaleString()} />
                  <Legend />
                  <Line type="monotone" dataKey="total_prs" stroke="#0066cc" name="Total PRs" />
                  <Line type="monotone" dataKey="unassigned_count" stroke="#ff6b6b" name="Unassigned" />
                  <Line type="monotone" dataKey="old_prs_count" stroke="#ffa500" name="Old PRs" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {stats?.reviewers && stats.reviewers.length > 0 && (
            <div className="chart-container">
              <h2>Current Reviewer Workload</h2>
              <p style={{ color: '#666', marginBottom: '15px' }}>
                Number of open PRs assigned to each reviewer and total comments made
              </p>
              <ResponsiveContainer width="100%" height={Math.max(400, stats.reviewers.length * 40)}>
                <BarChart data={stats.reviewers} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis 
                    dataKey="reviewer" 
                    type="category" 
                    width={150}
                    interval={0}
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" fill="#0066cc" name="PRs Assigned" />
                  <Bar dataKey="comments" fill="#ffa500" name="Comments Made" />
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
              <h2>PRs in Snapshot</h2>
              {prs.map(pr => (
                <div key={pr.id} className="pr-item">
                  <div className="pr-title">
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
        </>
      )}

      {activeTab === 'historical' && (
        <div className="historical-import">
          <div className="form-container">
            <h2>Import Historical Snapshots</h2>
            <p className="description">
              Import weekly snapshots for a date range. The system will fetch PRs that were open at each weekly interval.
            </p>

            <div className="form-group">
              <label htmlFor="startDate">Start Date (required)</label>
              <input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={historicalImporting}
              />
            </div>

            <div className="form-group">
              <label htmlFor="endDate">End Date (optional, defaults to today)</label>
              <input
                id="endDate"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={historicalImporting}
              />
            </div>

            <button
              onClick={handleHistoricalImport}
              disabled={historicalImporting || !startDate}
              className="import-button large"
            >
              {historicalImporting ? 'Importing Historical Data...' : 'Start Import'}
            </button>

            {historicalImporting && currentWeek && (
              <div className="progress-container">
                <div className="progress-info">
                  <span>Processing week: {currentWeek}</span>
                  <span>{progressPercent}%</span>
                </div>
                <div className="progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            )}

            {historicalMessage && (
              <div className={`message ${historicalMessage.type}`}>
                {historicalMessage.text}
              </div>
            )}

            {importProgress && (
              <div className="progress-summary">
                <h3>Import Summary</h3>
                <div className="progress-stats">
                  <div className="progress-stat">
                    <span className="progress-label">Total Dates:</span>
                    <span className="progress-value">{importProgress.total}</span>
                  </div>
                  <div className="progress-stat success">
                    <span className="progress-label">Imported:</span>
                    <span className="progress-value">{importProgress.imported}</span>
                  </div>
                  <div className="progress-stat warning">
                    <span className="progress-label">Skipped (duplicates):</span>
                    <span className="progress-value">{importProgress.skipped}</span>
                  </div>
                  <div className="progress-stat error">
                    <span className="progress-label">Failed:</span>
                    <span className="progress-value">{importProgress.failed}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="info-box">
              <h3>How it works</h3>
              <ul>
                <li>Generates weekly dates from start to end date</li>
                <li>For each date, fetches PRs that were open at that time</li>
                <li>Automatically skips dates that already have snapshots</li>
                <li>May take several minutes depending on date range</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
