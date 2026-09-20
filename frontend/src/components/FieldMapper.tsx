import React, { useState, useEffect, useRef } from 'react'

interface FieldMapping {
  [key: string]: string
}

interface FieldMapperProps {
  headers: string[]
  sampleData: any[][]
  onMappingComplete: (mapping: FieldMapping, rowIndex?: any) => void
  onMappingChange: (mapping: FieldMapping) => void
}

const FieldMapper: React.FC<FieldMapperProps> = ({ 
  headers, 
  sampleData, 
  onMappingComplete, 
  onMappingChange 
}) => {
  const [mapping, setMapping] = useState<FieldMapping>({})
  const [suggestions, setSuggestions] = useState<FieldMapping>({})
  const [createRowIndex, setCreateRowIndex] = useState<boolean>(false)

  const fieldTypes = [
    { value: 'review_text', label: 'Review Text', required: true },
    { value: 'record_id', label: 'Record ID', required: false },
    { value: 'timestamp', label: 'Timestamp', required: false },
    { value: 'rating', label: 'Rating', required: false },
    { value: 'language', label: 'Language', required: false },
    { value: 'product', label: 'Product', required: false },
    { value: 'source', label: 'Source', required: false },
    { value: 'other', label: 'Other', required: false }
  ]

  const initializedFor = useRef<string>('')

  useEffect(() => {
    // Initialize mapping state from inferred defaults when headers load
    const key = headers.join('|')
    if (headers.length > 0 && initializedFor.current !== key) {
      initializedFor.current = key
      const initial = generateSuggestions()
      setSuggestions(initial)
      setMapping(initial)
      // Default to a generated row index when no Record ID column exists
      setCreateRowIndex(!Object.values(initial).includes('record_id'))
      onMappingChange(initial)
    }
  }, [headers, sampleData])

  const inferFieldType = (header: string): string => {
    const h = header.toLowerCase()
    const tokens = h.split(/[^a-z0-9]+/).filter(Boolean)

    // Exact/strong field-name matching
    if (h === 'record_id' || h === 'id' || tokens.includes('record')) return 'record_id'
    if (h === 'review_text' || h === 'review' || h === 'reviewtext') return 'review_text'
    if (h === 'source_url' || h === 'url' || h === 'link') return 'source'

    // Fields containing an 'id' token are identifiers, never review text
    const isIdField = tokens.includes('id')

    if (!isIdField) {
      if (h.includes('review') || h.includes('text') ||
          h.includes('comment') || h.includes('content')) {
        return 'review_text'
      }
    }

    if (isIdField) return 'other'
    if (h.includes('key')) return 'record_id'
    if (h.includes('date') || h.includes('time')) return 'timestamp'
    if (h.includes('rating') || h.includes('score') || h.includes('star')) return 'rating'
    if (h.includes('language') || h.includes('lang')) return 'language'
    if (h.includes('product') || h.includes('item')) return 'product'
    if (h.includes('source') || h.includes('origin')) return 'source'
    return 'other'
  }

  const generateSuggestions = (): FieldMapping => {
    const newSuggestions: FieldMapping = {}
    let reviewTextAssigned = false

    headers.forEach((header) => {
      let fieldType = inferFieldType(header)
      // Only one column can be the primary Review Text field
      if (fieldType === 'review_text') {
        if (reviewTextAssigned) {
          fieldType = 'other'
        } else {
          reviewTextAssigned = true
        }
      }
      newSuggestions[header] = fieldType
    })

    return newSuggestions
  }

  const handleMappingChange = (header: string, fieldType: string) => {
    const newMapping = { ...mapping, [header]: fieldType }
    // Enforce single primary Review Text field
    if (fieldType === 'review_text') {
      Object.keys(newMapping).forEach(key => {
        if (key !== header && newMapping[key] === 'review_text') {
          newMapping[key] = 'other'
        }
      })
    }
    setMapping(newMapping)
    onMappingChange(newMapping)
  }

  const isBlankRow = (row: any): boolean => {
    if (!row) return true
    const cells = Array.isArray(row) ? row : Object.values(row)
    return cells.every(c => c === undefined || c === null || !String(c).trim())
  }

  const nonEmptyRowCount = sampleData.filter(row => !isBlankRow(row)).length

  // Check a mapped Record ID column for blank or duplicate values
  const getRecordIdIssues = () => {
    const column = headers.find(h => mapping[h] === 'record_id')
    if (!column) return null
    const index = headers.indexOf(column)
    const values = sampleData
      .filter(row => !isBlankRow(row))
      .map(row => {
        const v = Array.isArray(row) ? row[index] : row?.[column]
        return v === undefined || v === null ? '' : String(v).trim()
      })
    const blankCount = values.filter(v => !v).length
    const seen = new Set<string>()
    let duplicateCount = 0
    values.forEach(v => {
      if (v) {
        if (seen.has(v)) duplicateCount++
        else seen.add(v)
      }
    })
    return blankCount + duplicateCount > 0 ? { column, blankCount, duplicateCount } : null
  }

  const recordIdIssues = getRecordIdIssues()
  const recordIdValid = !recordIdIssues &&
    Object.values(mapping).includes('record_id')

  const generateRowIndex = () => {
    const entries: { id: string; source_row: number }[] = []
    sampleData.forEach((row, i) => {
      // Blank rows get no ID and do not shift source-row traceability
      if (!isBlankRow(row)) {
        entries.push({
          id: `ROW-${String(entries.length + 1).padStart(6, '0')}`,
          source_row: i + 1
        })
      }
    })
    return entries
  }

  const validateMapping = (currentMapping: FieldMapping) => {
    const mappedTypes = Object.values(currentMapping)
    const reviewTextCount = mappedTypes.filter(t => t === 'review_text').length

    const errors = []
    if (reviewTextCount === 0) {
      errors.push('Review Text field is required')
    } else if (reviewTextCount > 1) {
      errors.push('Only one column can be the Review Text field')
    }

    return {
      valid: errors.length === 0 && (recordIdValid || createRowIndex),
      errors,
      requiredFields: reviewTextCount === 1 ? 1 : 0,
      mappedFields: mappedTypes.filter(t => t !== 'other').length
    }
  }

  // Derive summary state directly from current mapping so it always
  // matches the visible selections
  const currentValidation = validateMapping(mapping)

  const handleComplete = () => {
    if (currentValidation.valid) {
      const rowIndex = createRowIndex
        ? { mode: 'generated', entries: generateRowIndex() }
        : { mode: 'column', column: headers.find(h => mapping[h] === 'record_id') }
      onMappingComplete({ ...mapping }, rowIndex)
    }
  }

  const getFieldTypeColor = (fieldType: string) => {
    const colors: { [key: string]: string } = {
      'review_text': 'var(--info-soft)',
      'record_id': 'var(--primary-soft)',
      'timestamp': 'var(--success-soft)',
      'rating': 'var(--warning-soft)',
      'language': 'var(--danger-soft)',
      'product': 'var(--success-soft)',
      'source': 'var(--success-soft)',
      'other': 'var(--surface-2)'
    }
    return colors[fieldType] || 'var(--surface-2)'
  }

  const getFieldTypeIcon = (fieldType: string) => {
    const icons: { [key: string]: string } = {
      'review_text': '📝',
      'record_id': '🆔',
      'timestamp': '📅',
      'rating': '⭐',
      'language': '🌐',
      'product': '📦',
      'source': '🔗',
      'other': '📋'
    }
    return icons[fieldType] || '📋'
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Field Mapping</h3>
      <p>Map your data columns to the appropriate fields for classification.</p>
      
      {/* Validation Status */}
      {currentValidation.errors.length > 0 && (
        <div style={{ 
          padding: '10px', 
          backgroundColor: 'var(--danger-soft)', 
          border: '1px solid var(--danger)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '20px'
        }}>
          <strong style={{ color: 'var(--danger)' }}>Validation Errors:</strong>
          <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px' }}>
            {currentValidation.errors.map((error: string, index: number) => (
              <li key={index} style={{ color: 'var(--danger)' }}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Record ID warnings */}
      {!Object.values(mapping).includes('record_id') && (
        <div style={{ 
          padding: '10px', 
          backgroundColor: 'var(--warning-soft)', 
          border: '1px solid var(--warning)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '20px'
        }}>
          <strong style={{ color: 'var(--warning)' }}>No Record ID detected.</strong>{' '}
          Create a row index for tracking and sampling.
          <div style={{ marginTop: '8px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={createRowIndex}
                onChange={(e) => setCreateRowIndex(e.target.checked)}
              />
              Create Row Index — generate immutable IDs for {nonEmptyRowCount} non-empty records
            </label>
          </div>
        </div>
      )}

      {recordIdIssues && (
        <div style={{ 
          padding: '10px', 
          backgroundColor: 'var(--warning-soft)', 
          border: '1px solid var(--warning)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '20px'
        }}>
          <strong style={{ color: 'var(--warning)' }}>Record ID issues in "{recordIdIssues.column}":</strong>{' '}
          {recordIdIssues.blankCount} blank, {recordIdIssues.duplicateCount} duplicate value(s).
          <div style={{ marginTop: '8px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={createRowIndex}
                onChange={(e) => setCreateRowIndex(e.target.checked)}
              />
              Create Row Index instead — generate immutable IDs for {nonEmptyRowCount} non-empty records
            </label>
          </div>
        </div>
      )}

      {/* Mapping Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ 
          width: '100%', 
          borderCollapse: 'collapse', 
          border: '1px solid var(--border)' 
        }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--surface-2)' }}>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>
                Column Name
              </th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>
                Sample Data
              </th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>
                Field Type
              </th>
            </tr>
          </thead>
          <tbody>
            {headers.map((header, index) => (
              <tr key={index} style={{ 
                backgroundColor: getFieldTypeColor(mapping[header] || 'other')
              }}>
                <td style={{ 
                  padding: '10px', 
                  borderBottom: '1px solid var(--border)',
                  fontWeight: 'bold'
                }}>
                  {header}
                </td>
                <td style={{ 
                  padding: '10px', 
                  borderBottom: '1px solid var(--border)',
                  fontSize: '12px',
                  color: 'var(--text-2)',
                  maxWidth: '200px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}>
                  {sampleData.slice(0, 3).map((row, i) => {
                    const value = Array.isArray(row) ? row[index] : row?.[header]
                    return (
                      <div key={i} style={{ marginBottom: '2px' }}>
                        {value !== undefined && value !== null ? String(value) : ''}
                      </div>
                    )
                  })}
                </td>
                <td style={{ padding: '10px', borderBottom: '1px solid var(--border)' }}>
                  <select
                    value={mapping[header] || 'other'}
                    onChange={(e) => handleMappingChange(header, e.target.value)}
                    style={{ 
                      width: '100%', 
                      padding: '6px', 
                      border: '1px solid var(--border)', 
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'white'
                    }}
                  >
                    {fieldTypes.map(field => (
                      <option key={field.value} value={field.value}>
                        {getFieldTypeIcon(field.value)} {field.label}
                        {field.required ? ' (Required)' : ''}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mapping Summary */}
      <div style={{ 
        marginTop: '20px', 
        padding: '15px', 
        backgroundColor: 'var(--surface-2)', 
        borderRadius: 'var(--radius-sm)' 
      }}>
        <h4>Mapping Summary</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
          <div>
            <strong>Required Fields:</strong> {currentValidation.requiredFields}/1
          </div>
          <div>
            <strong>Total Mapped:</strong> {currentValidation.mappedFields}/{headers.length}
          </div>
          <div>
            <strong>Status:</strong> 
            <span style={{ 
              color: currentValidation.valid ? 'var(--success)' : 'var(--danger)',
              fontWeight: 'bold',
              marginLeft: '5px'
            }}>
              {currentValidation.valid ? 'Valid' : 'Invalid'}
            </span>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ marginTop: '20px', textAlign: 'center' }}>
        <button
          onClick={handleComplete}
          disabled={!currentValidation.valid}
          style={{ 
            padding: '12px 24px',
            backgroundColor: currentValidation.valid ? 'var(--success)' : 'var(--border)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: currentValidation.valid ? 'pointer' : 'not-allowed',
            fontSize: '16px'
          }}
        >
          Complete Field Mapping
        </button>
      </div>
    </div>
  )
}

export default FieldMapper
