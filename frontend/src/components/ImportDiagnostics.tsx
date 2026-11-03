import React from 'react'

interface DiagnosticIssue {
  type: string
  severity: 'error' | 'warning' | 'info'
  message: string
  suggestion?: string
}

interface DiagnosticsProps {
  diagnostics: {
    parse_status: string
    issues: DiagnosticIssue[]
    warnings: DiagnosticIssue[]
    summary: {
      total_rows: number
      preview_rows: number
      total_columns: number
      file_type: string
      encoding?: string
      delimiter?: string
      sheet_name?: string
    }
    recommendations: string[]
  }
}

const ImportDiagnostics: React.FC<DiagnosticsProps> = ({ diagnostics }) => {
  const { issues, warnings, summary, recommendations } = diagnostics

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'error': return 'var(--danger)'
      case 'warning': return 'var(--warning)'
      case 'info': return 'var(--info)'
      default: return 'var(--text-2)'
    }
  }

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'error': return '✗'
      case 'warning': return '!'
      case 'info': return 'i'
      default: return '·'
    }
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Import Diagnostics</h3>
      
      {/* Summary */}
      <div style={{ 
        backgroundColor: 'var(--info-soft)', 
        padding: '15px', 
        borderRadius: 'var(--radius-sm)', 
        marginBottom: '20px' 
      }}>
        <h4 style={{ margin: '0 0 10px 0' }}>Summary</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
          <div><strong>Status:</strong> {diagnostics.parse_status}</div>
          <div><strong>Rows:</strong> {summary.total_rows.toLocaleString()}</div>
          <div><strong>Columns:</strong> {summary.total_columns}</div>
          <div><strong>File Type:</strong> {summary.file_type}</div>
          {summary.encoding && <div><strong>Encoding:</strong> {summary.encoding}</div>}
          {summary.delimiter && <div><strong>Delimiter:</strong> {summary.delimiter}</div>}
          {summary.sheet_name && <div><strong>Sheet:</strong> {summary.sheet_name}</div>}
        </div>
      </div>

      {/* Issues */}
      {issues.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ color: 'var(--danger)' }}>Issues ({issues.length})</h4>
          {issues.map((issue, index) => (
            <div 
              key={index}
              style={{ 
                padding: '10px', 
                margin: '5px 0', 
                backgroundColor: 'var(--danger-soft)', 
                borderLeft: '4px solid var(--danger)',
                borderRadius: '0 4px 4px 0'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>{getSeverityIcon(issue.severity)}</span>
                <strong style={{ color: getSeverityColor(issue.severity) }}>
                  {issue.type.replace(/_/g, ' ').toUpperCase()}
                </strong>
              </div>
              <div style={{ marginTop: '5px' }}>{issue.message}</div>
              {issue.suggestion && (
                <div style={{ 
                  marginTop: '5px', 
                  fontSize: '14px', 
                  color: 'var(--text-2)',
                  fontStyle: 'italic'
                }}>
                  Suggestion: {issue.suggestion}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ color: 'var(--warning)' }}>Warnings ({warnings.length})</h4>
          {warnings.map((warning, index) => (
            <div 
              key={index}
              style={{ 
                padding: '10px', 
                margin: '5px 0', 
                backgroundColor: 'var(--warning-soft)', 
                borderLeft: '4px solid var(--warning)',
                borderRadius: '0 4px 4px 0'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>{getSeverityIcon(warning.severity)}</span>
                <strong style={{ color: getSeverityColor(warning.severity) }}>
                  {warning.type.replace(/_/g, ' ').toUpperCase()}
                </strong>
              </div>
              <div style={{ marginTop: '5px' }}>{warning.message}</div>
              {warning.suggestion && (
                <div style={{ 
                  marginTop: '5px', 
                  fontSize: '14px', 
                  color: 'var(--text-2)',
                  fontStyle: 'italic'
                }}>
                  Suggestion: {warning.suggestion}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <h4 style={{ color: 'var(--success)' }}>Recommendations</h4>
          <ul style={{ 
            backgroundColor: 'var(--success-soft)', 
            padding: '15px', 
            borderRadius: 'var(--radius-sm)',
            margin: 0,
            paddingLeft: '30px'
          }}>
            {recommendations.map((rec, index) => (
              <li key={index} style={{ margin: '5px 0' }}>{rec}</li>
            ))}
          </ul>
        </div>
      )}

      {/* No Issues */}
      {issues.length === 0 && warnings.length === 0 && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: 'var(--success-soft)', 
          borderRadius: 'var(--radius-sm)',
          textAlign: 'center',
          color: 'var(--success)'
        }}>
          <div style={{ fontSize: '24px', marginBottom: '10px' }}>✓</div>
          <div style={{ fontWeight: 'bold' }}>No issues detected</div>
          <div style={{ fontSize: '14px', marginTop: '5px' }}>
            File appears to be ready for processing
          </div>
        </div>
      )}
    </div>
  )
}

export default ImportDiagnostics
