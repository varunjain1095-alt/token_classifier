import React, { useState, useEffect } from 'react'

interface Execution {
  id: string
  created_at: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  total_records: number
  processed_records: number
  successful_records: number
  failed_records: number
  estimated_cost: number
  actual_cost: number
  current_batch: number
  total_batches: number
  token_usage: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
}

interface ClassificationExecutorProps {
  datasetRecords: any[]
  experimentConfig: any
  categorySet: any
  apiKey: string
  estimatedCost: number
  onExecutionComplete: (execution: any) => void
}

const ClassificationExecutor: React.FC<ClassificationExecutorProps> = ({ 
  datasetRecords, 
  experimentConfig, 
  categorySet, 
  apiKey, 
  estimatedCost, 
  onExecutionComplete 
}) => {
  const [execution, setExecution] = useState<Execution | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState<boolean>(false)

  useEffect(() => {
    let interval: NodeJS.Timeout
    if (autoRefresh && execution && execution.status === 'running') {
      interval = setInterval(() => {
        refreshExecutionStatus()
      }, 2000) // Refresh every 2 seconds
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [autoRefresh, execution])

  const startExecution = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/execution/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          dataset_records: datasetRecords,
          experiment_config: experimentConfig,
          category_set: categorySet,
          api_key: apiKey,
          estimated_cost: estimatedCost
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        setExecution(data.execution)
        setAutoRefresh(true)
        onExecutionComplete(data.execution)
      } else {
        setError(data.error || 'Failed to start execution')
      }
    } catch (error) {
      setError('Execution start failed: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const refreshExecutionStatus = async () => {
    if (!execution) return
    
    try {
      const response = await fetch(`/api/execution/status/${execution.id}`)
      const data = await response.json()
      
      if (data.success) {
        setExecution(data.execution)
        
        // Stop auto-refresh if execution is complete
        if (data.execution.status !== 'running') {
          setAutoRefresh(false)
        }
      }
    } catch (error) {
      console.error('Failed to refresh status:', error)
    }
  }

  const pauseExecution = async () => {
    if (!execution) return
    
    try {
      const response = await fetch(`/api/execution/pause/${execution.id}`, {
        method: 'POST'
      })
      const data = await response.json()
      
      if (data.success) {
        setAutoRefresh(false)
        await refreshExecutionStatus()
      }
    } catch (error) {
      console.error('Failed to pause execution:', error)
    }
  }

  const resumeExecution = async () => {
    if (!execution) return
    
    try {
      const response = await fetch(`/api/execution/resume/${execution.id}`, {
        method: 'POST'
      })
      const data = await response.json()
      
      if (data.success) {
        setAutoRefresh(true)
        await refreshExecutionStatus()
      }
    } catch (error) {
      console.error('Failed to resume execution:', error)
    }
  }

  const cancelExecution = async () => {
    if (!execution) return
    
    try {
      const response = await fetch(`/api/execution/cancel/${execution.id}`, {
        method: 'POST'
      })
      const data = await response.json()
      
      if (data.success) {
        setAutoRefresh(false)
        await refreshExecutionStatus()
      }
    } catch (error) {
      console.error('Failed to cancel execution:', error)
    }
  }

  const getStatusColor = (status: string) => {
    const colors = {
      'pending': 'var(--warning)',
      'running': 'var(--info)',
      'paused': 'var(--primary)',
      'completed': 'var(--success)',
      'failed': 'var(--danger)',
      'cancelled': 'var(--text-2)'
    }
    return colors[status as keyof typeof colors] || 'var(--text-2)'
  }

  const getStatusIcon = (status: string) => {
    const icons = {
      'pending': '⏳',
      'running': '🔄',
      'paused': '⏸️',
      'completed': '✅',
      'failed': '❌',
      'cancelled': '🚫'
    }
    return icons[status as keyof typeof icons] || '📋'
  }

  const progress = execution ? (execution.processed_records / execution.total_records) * 100 : 0

  if (error) {
    return (
      <div style={{ 
        padding: '20px', 
        backgroundColor: 'var(--danger-soft)', 
        border: '1px solid var(--danger)',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--danger)'
      }}>
        <strong>Error:</strong> {error}
      </div>
    )
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Full Classification Execution</h3>
      <p>Process your entire dataset with the configured AI classification.</p>
      
      {/* Execution Controls */}
      {!execution ? (
        <div style={{ 
          padding: '30px', 
          textAlign: 'center', 
          backgroundColor: 'var(--surface-2)', 
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border)'
        }}>
          <div style={{ fontSize: '18px', marginBottom: '20px' }}>
            🚀 Ready to Process {datasetRecords.length.toLocaleString()} Records
          </div>
          
          <div style={{ marginBottom: '20px', fontSize: '14px', color: 'var(--text-2)' }}>
            <div>Estimated Cost: ${estimatedCost.toFixed(6)}</div>
            <div>Model: {experimentConfig?.config?.model || 'configured preview model'}</div>
            <div>Categories: {categorySet?.categories?.length || 0}</div>
          </div>
          
          <button
            onClick={startExecution}
            disabled={loading}
            style={{
              padding: '15px 30px',
              backgroundColor: 'var(--success)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              fontSize: '16px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            {loading ? 'Starting Execution...' : 'Start Classification'}
          </button>
        </div>
      ) : (
        <div style={{ 
          padding: '20px', 
          backgroundColor: 'var(--surface)', 
          border: '2px solid var(--border)',
          borderRadius: 'var(--radius)'
        }}>
          {/* Status Header */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '20px',
            paddingBottom: '15px',
            borderBottom: '1px solid var(--border)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '24px' }}>{getStatusIcon(execution.status)}</span>
              <div>
                <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
                  {execution.status.charAt(0).toUpperCase() + execution.status.slice(1)}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                  Execution ID: {execution.id.slice(0, 8)}...
                </div>
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '10px' }}>
              {execution.status === 'running' && (
                <>
                  <button
                    onClick={pauseExecution}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: 'var(--warning)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer'
                    }}
                  >
                    Pause
                  </button>
                  <button
                    onClick={cancelExecution}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: 'var(--danger)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer'
                    }}
                  >
                    Cancel
                  </button>
                </>
              )}
              
              {execution.status === 'paused' && (
                <>
                  <button
                    onClick={resumeExecution}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: 'var(--success)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer'
                    }}
                  >
                    Resume
                  </button>
                  <button
                    onClick={cancelExecution}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: 'var(--danger)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer'
                    }}
                  >
                    Cancel
                  </button>
                </>
              )}
              
              {execution.status === 'completed' && (
                <button
                  onClick={() => window.open(`/api/execution/results/${execution.id}`, '_blank')}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: 'var(--info)',
                    color: 'white',
                    border: 'none',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer'
                  }}
                >
                  Download Results
                </button>
              )}
            </div>
          </div>

          {/* Progress Bar */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              marginBottom: '5px',
              fontSize: '14px'
            }}>
              <span>Progress: {execution.processed_records.toLocaleString()} / {execution.total_records.toLocaleString()}</span>
              <span>{progress.toFixed(1)}%</span>
            </div>
            
            <div style={{ 
              width: '100%', 
              height: '20px', 
              backgroundColor: 'var(--border)', 
              borderRadius: 'var(--radius-sm)',
              overflow: 'hidden'
            }}>
              <div style={{ 
                width: `${progress}%`, 
                height: '100%', 
                backgroundColor: getStatusColor(execution.status),
                transition: 'width 0.3s ease'
              }} />
            </div>
            
            <div style={{ 
              marginTop: '5px', 
              fontSize: '12px', 
              color: 'var(--text-2)',
              textAlign: 'center'
            }}>
              Batch {execution.current_batch} of {execution.total_batches}
            </div>
          </div>

          {/* Statistics */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
            gap: '15px',
            marginBottom: '20px'
          }}>
            <div style={{ 
              textAlign: 'center', 
              padding: '15px', 
              backgroundColor: 'var(--success-soft)', 
              borderRadius: 'var(--radius-sm)' 
            }}>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--success)' }}>
                {execution.successful_records.toLocaleString()}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Successful</div>
            </div>
            
            <div style={{ 
              textAlign: 'center', 
              padding: '15px', 
              backgroundColor: 'var(--danger-soft)', 
              borderRadius: 'var(--radius-sm)' 
            }}>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--danger)' }}>
                {execution.failed_records.toLocaleString()}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Failed</div>
            </div>
            
            <div style={{ 
              textAlign: 'center', 
              padding: '15px', 
              backgroundColor: 'var(--info-soft)', 
              borderRadius: 'var(--radius-sm)' 
            }}>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--info)' }}>
                ${execution.actual_cost.toFixed(6)}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Actual Cost</div>
            </div>
            
            <div style={{ 
              textAlign: 'center', 
              padding: '15px', 
              backgroundColor: 'var(--warning-soft)', 
              borderRadius: 'var(--radius-sm)' 
            }}>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--warning)' }}>
                {execution.token_usage.total_tokens.toLocaleString()}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Tokens Used</div>
            </div>
          </div>

          {/* Execution Details */}
          {execution.status === 'completed' && (
            <div style={{ 
              padding: '15px', 
              backgroundColor: 'var(--success-soft)', 
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--success)'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '10px' }}>✅ Execution Completed Successfully</div>
              <div style={{ fontSize: '14px' }}>
                <div>• Processed {execution.processed_records.toLocaleString()} records</div>
                <div>• Success rate: {((execution.successful_records / execution.processed_records) * 100).toFixed(1)}%</div>
                <div>• Total cost: ${execution.actual_cost.toFixed(6)}</div>
                <div>• Total tokens: {execution.token_usage.total_tokens.toLocaleString()}</div>
                <div>• Completed at: {new Date(execution.created_at).toLocaleString()}</div>
              </div>
            </div>
          )}

          {execution.status === 'failed' && (
            <div style={{ 
              padding: '15px', 
              backgroundColor: 'var(--danger-soft)', 
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--danger)'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '10px' }}>❌ Execution Failed</div>
              <div style={{ fontSize: '14px' }}>
                Check the logs for more details about the failure.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ClassificationExecutor
