import React, { useState, useEffect } from 'react'

interface Export {
  id: string
  execution_id: string
  export_type: string
  export_format: string
  created_at: string
  status: 'processing' | 'generating' | 'completed' | 'failed'
  file_size: number
  record_count: number
}

interface ExportStatistics {
  total_exports: number
  completed_exports: number
  failed_exports: number
  success_rate: number
  format_distribution: { [key: string]: number }
  type_distribution: { [key: string]: number }
}

interface ExportManagerProps {
  executionResults: any
  onExportComplete: (exportData: any) => void
}

const ExportManager: React.FC<ExportManagerProps> = ({ executionResults, onExportComplete }) => {
  const [exports, setExports] = useState<Export[]>([])
  const [statistics, setStatistics] = useState<ExportStatistics | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string>('full_report')
  const [selectedFormat, setSelectedFormat] = useState<string>('csv')
  const [includeMetadata, setIncludeMetadata] = useState<boolean>(true)

  useEffect(() => {
    loadExports()
    loadStatistics()
  }, [])

  const loadExports = async () => {
    try {
      const response = await fetch('/api/export/list', { credentials: 'include' })
      const data = await response.json()
      if (data.success) {
        setExports(data.exports || [])
      }
    } catch (error) {
      console.error('Failed to load exports:', error)
    }
  }

  const loadStatistics = async () => {
    try {
      const response = await fetch('/api/export/statistics', { credentials: 'include' })
      const data = await response.json()
      if (data.success) {
        setStatistics(data.statistics)
      }
    } catch (error) {
      console.error('Failed to load statistics:', error)
    }
  }

  const createExport = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/export/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          execution_id: executionResults?.execution_id,
          export_type: selectedType,
          export_format: selectedFormat,
          include_metadata: includeMetadata
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        await loadExports()
        await loadStatistics()
        onExportComplete(data.export)
      } else {
        setError(data.error || 'Failed to create export')
      }
    } catch (error) {
      setError('Export creation failed: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const downloadExport = async (exportItem: Export) => {
    try {
      const response = await fetch(`/api/export/download/${exportItem.id}`,
        { credentials: 'include' })
      if (!response.ok) {
        setError(`Export download failed (${response.status})`)
        return
      }
      const ext = exportItem.export_format === 'excel' ? 'xlsx' : exportItem.export_format
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `export_${exportItem.id.slice(0, 8)}.${ext}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Failed to download export:', error)
    }
  }

  const deleteExport = async (exportId: string) => {
    try {
      const response = await fetch(`/api/export/${exportId}`, {
        method: 'DELETE',
        credentials: 'include'
      })
      const data = await response.json()
      if (data.success) {
        await loadExports()
        await loadStatistics()
      }
    } catch (error) {
      console.error('Failed to delete export:', error)
    }
  }

  const getStatusColor = (status: string) => {
    const colors = {
      'processing': 'var(--warning)',
      'generating': 'var(--info)',
      'completed': 'var(--success)',
      'failed': 'var(--danger)'
    }
    return colors[status as keyof typeof colors] || 'var(--text-2)'
  }

  const getStatusIcon = (status: string) => {
    const icons = {
      'processing': '⏳',
      'generating': '🔄',
      'completed': '✅',
      'failed': '❌'
    }
    return icons[status as keyof typeof icons] || '📋'
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const exportTypes = [
    { value: 'results_only', label: 'Results Only', description: 'Classification results only' },
    { value: 'full_report', label: 'Full Report', description: 'Complete report with all data' },
    { value: 'summary', label: 'Summary', description: 'Summary statistics only' },
    { value: 'raw_data', label: 'Raw Data', description: 'All raw execution data' }
  ]

  const exportFormats = [
    { value: 'csv', label: 'CSV', description: 'Comma-separated values' },
    { value: 'xlsx', label: 'Excel', description: 'Microsoft Excel workbook' },
    { value: 'json', label: 'JSON', description: 'JavaScript Object Notation' }
  ]

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Export & Reporting</h3>
      <p>Export your classification results in various formats for further analysis.</p>
      
      {/* Export Statistics */}
      {statistics && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: 'var(--surface-2)', 
          borderRadius: 'var(--radius-sm)',
          marginBottom: '30px',
          border: '1px solid var(--border)'
        }}>
          <h4>Export Statistics</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--info)' }}>
                {statistics.total_exports}
              </div>
              <div>Total Exports</div>
            </div>
            
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--success)' }}>
                {statistics.completed_exports}
              </div>
              <div>Completed</div>
            </div>
            
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--danger)' }}>
                {statistics.failed_exports}
              </div>
              <div>Failed</div>
            </div>
            
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--warning)' }}>
                {statistics.success_rate.toFixed(1)}%
              </div>
              <div>Success Rate</div>
            </div>
          </div>
        </div>
      )}

      {/* Create Export */}
      <div style={{ 
        padding: '20px', 
        backgroundColor: 'var(--surface)', 
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        marginBottom: '30px'
      }}>
        <h4>Create New Export</h4>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
              Export Type
            </label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              style={{ 
                width: '100%', 
                padding: '8px', 
                border: '1px solid var(--border)', 
                borderRadius: 'var(--radius-sm)' 
              }}
            >
              {exportTypes.map(type => (
                <option key={type.value} value={type.value}>
                  {type.label} - {type.description}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
              Export Format
            </label>
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value)}
              style={{ 
                width: '100%', 
                padding: '8px', 
                border: '1px solid var(--border)', 
                borderRadius: 'var(--radius-sm)' 
              }}
            >
              {exportFormats.map(format => (
                <option key={format.value} value={format.value}>
                  {format.label} - {format.description}
                </option>
              ))}
            </select>
          </div>
        </div>
        
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="checkbox"
              checked={includeMetadata}
              onChange={(e) => setIncludeMetadata(e.target.checked)}
            />
            Include metadata (execution info, timestamps, etc.)
          </label>
        </div>
        
        <button
          onClick={createExport}
          disabled={loading || !executionResults}
          style={{
            padding: '12px 24px',
            backgroundColor: 'var(--primary)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: loading || !executionResults ? 'not-allowed' : 'pointer',
            opacity: loading || !executionResults ? 0.6 : 1
          }}
        >
          {loading ? 'Creating Export...' : 'Create Export'}
        </button>
      </div>

      {/* Export History */}
      <div>
        <h4>Export History</h4>
        
        {exports.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '40px', 
            color: 'var(--text-2)',
            backgroundColor: 'var(--surface-2)',
            borderRadius: 'var(--radius-sm)'
          }}>
            No exports created yet.
          </div>
        ) : (
          <div style={{ 
            border: '1px solid var(--border)', 
            borderRadius: 'var(--radius-sm)', 
            overflow: 'hidden' 
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--surface-2)' }}>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    Export
                  </th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    Type
                  </th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    Format
                  </th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    Status
                  </th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    Records
                  </th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    Size
                  </th>
                  <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    Created
                  </th>
                  <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid var(--border)' }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {exports.map((exportItem) => (
                  <tr key={exportItem.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '12px' }}>
                      <div style={{ fontSize: '14px', fontWeight: 'bold' }}>
                        {exportItem.id.slice(0, 8)}...
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                        Execution: {exportItem.execution_id.slice(0, 8)}...
                      </div>
                    </td>
                    <td style={{ padding: '12px' }}>
                      {exportItem.export_type.replace('_', ' ')}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {exportItem.export_format.toUpperCase()}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{ 
                        padding: '4px 8px', 
                        backgroundColor: getStatusColor(exportItem.status),
                        color: 'white',
                        borderRadius: '12px',
                        fontSize: '12px'
                      }}>
                        {getStatusIcon(exportItem.status)} {exportItem.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      {exportItem.record_count.toLocaleString()}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {formatFileSize(exportItem.file_size)}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {new Date(exportItem.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {exportItem.status === 'completed' && (
                        <button
                          onClick={() => downloadExport(exportItem)}
                          style={{
                            padding: '4px 8px',
                            backgroundColor: 'var(--info)',
                            color: 'white',
                            border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            cursor: 'pointer',
                            fontSize: '12px',
                            marginRight: '5px'
                          }}
                        >
                          Download
                        </button>
                      )}
                      <button
                        onClick={() => deleteExport(exportItem.id)}
                        style={{
                          padding: '4px 8px',
                          backgroundColor: 'var(--danger)',
                          color: 'white',
                          border: 'none',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                          fontSize: '12px'
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default ExportManager
