import React from 'react'

interface PreviewRow {
  [key: string]: any
}

interface FilePreviewProps {
  parseResult: {
    headers: string[]
    preview_rows: any[][]
    total_rows: number
    file_type: string
    encoding?: string
    delimiter?: string
    sheet_name?: string
  }
}

const FilePreview: React.FC<FilePreviewProps> = ({ parseResult }) => {
  if (!parseResult) return null
  const { headers = [], preview_rows = [], total_rows = 0, file_type = '', encoding, delimiter, sheet_name } = parseResult

  const getFileTypeDisplay = () => {
    switch (file_type) {
      case 'csv': return 'CSV'
      case 'xlsx': return 'Excel (XLSX)'
      case 'xls': return 'Excel (XLS)'
      default: return file_type.toUpperCase()
    }
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>File Preview</h3>
      
      {/* File Info */}
      <div style={{ 
        backgroundColor: 'var(--surface-2)', 
        padding: '15px', 
        borderRadius: 'var(--radius-sm)', 
        marginBottom: '20px' 
      }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <strong>File Type:</strong> {getFileTypeDisplay()}
          </div>
          {encoding && (
            <div>
              <strong>Encoding:</strong> {encoding}
            </div>
          )}
          {delimiter && (
            <div>
              <strong>Delimiter:</strong> {delimiter === '\t' ? 'Tab' : delimiter}
            </div>
          )}
          {sheet_name && (
            <div>
              <strong>Sheet:</strong> {sheet_name}
            </div>
          )}
          <div>
            <strong>Total Rows:</strong> {total_rows.toLocaleString()}
          </div>
          <div>
            <strong>Columns:</strong> {headers.length}
          </div>
        </div>
      </div>

      {/* Data Preview */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ 
          width: '100%', 
          borderCollapse: 'collapse', 
          border: '1px solid var(--border)' 
        }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--surface-2)' }}>
              {headers.map((header, index) => (
                <th 
                  key={index}
                  style={{ 
                    padding: '10px', 
                    border: '1px solid var(--border)', 
                    textAlign: 'left',
                    fontWeight: 'bold',
                    minWidth: '120px'
                  }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview_rows.map((row, rowIndex) => (
              <tr key={rowIndex} style={{
                backgroundColor: rowIndex % 2 === 0 ? 'white' : 'var(--surface-2)'
              }}>
                {(Array.isArray(row) ? row : headers.map(h => row?.[h])).map((cell, cellIndex) => (
                  <td 
                    key={cellIndex}
                    style={{ 
                      padding: '8px', 
                      border: '1px solid var(--border)',
                      maxWidth: '200px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}
                    title={String(cell)}
                  >
                    {String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Preview Info */}
      <div style={{ 
        marginTop: '15px', 
        fontSize: '14px', 
        color: 'var(--text-2)',
        fontStyle: 'italic'
      }}>
        Showing first {preview_rows.length} rows of {total_rows.toLocaleString()} total rows
      </div>
    </div>
  )
}

export default FilePreview
