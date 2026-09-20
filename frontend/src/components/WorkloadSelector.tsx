import React, { useState, useEffect } from 'react'

interface EligibleRecord {
  record_id: string
  source_row: number
  review_text: string
  metadata: { [key: string]: any }
}

interface WorkloadSelectorProps {
  totalEligible: number
  eligibilityInfo?: { loaded: number; eligible: number; excluded: number } | null
  fileId?: string
  fieldMapping?: { [key: string]: string }
  useColumnIds?: boolean
  onWorkloadSelect: (selection: any) => void
  onValidationChange: (validation: any) => void
}

const WorkloadSelector: React.FC<WorkloadSelectorProps> = ({ 
  totalEligible,
  eligibilityInfo,
  fileId,
  fieldMapping = {},
  useColumnIds = true,
  onWorkloadSelect, 
  onValidationChange 
}) => {
  const [selectedMode, setSelectedMode] = useState<string>('all_eligible')
  const [customCount, setCustomCount] = useState<number>(1)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [seed, setSeed] = useState<number>(42)
  const [validation, setValidation] = useState<any>({})

  // Specific-rows table state
  const [records, setRecords] = useState<EligibleRecord[]>([])
  const [recordsTotal, setRecordsTotal] = useState<number>(0)
  const [page, setPage] = useState<number>(1)
  const [totalPages, setTotalPages] = useState<number>(1)
  const [pageSize] = useState<number>(25)
  const [search, setSearch] = useState<string>('')
  const [recordsLoading, setRecordsLoading] = useState<boolean>(false)
  const [recordsError, setRecordsError] = useState<string>('')

  const workloadModes = [
    { value: 'all_eligible', label: 'All Eligible Records', description: 'Use all eligible records' },
    { value: 'percentage_25', label: '25% Sample', description: '25% of eligible records' },
    { value: 'percentage_50', label: '50% Sample', description: '50% of eligible records' },
    { value: 'percentage_75', label: '75% Sample', description: '75% of eligible records' },
    { value: 'custom_count', label: 'Custom Count', description: 'Specific number of records' },
    { value: 'specific_rows', label: 'Specific Rows', description: 'Manually selected rows' }
  ]

  useEffect(() => {
    validateSelection()
  }, [selectedMode, customCount, selectedIds, totalEligible])

  // Load eligible records from the stored snapshot when Specific Rows is active
  useEffect(() => {
    if (selectedMode !== 'specific_rows' || !fileId) return
    const loadRecords = async () => {
      setRecordsLoading(true)
      setRecordsError('')
      try {
        const response = await fetch('/api/eligibility/records', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            file_id: fileId,
            field_mapping: fieldMapping,
            use_column_ids: useColumnIds,
            page,
            page_size: pageSize,
            search
          })
        })
        const data = await response.json()
        if (data.success) {
          setRecords(data.records)
          setRecordsTotal(data.total_eligible)
          setTotalPages(data.total_pages)
        } else {
          setRecordsError('Failed to load eligible records')
        }
      } catch (e) {
        setRecordsError('Failed to load eligible records')
      } finally {
        setRecordsLoading(false)
      }
    }
    loadRecords()
  }, [selectedMode, fileId, page, search])

  const validateSelection = () => {
    const errors = []
    let estimatedCount = 0

    switch (selectedMode) {
      case 'all_eligible':
        estimatedCount = totalEligible
        break
      case 'percentage_25':
        estimatedCount = Math.max(1, Math.round(totalEligible * 0.25))
        break
      case 'percentage_50':
        estimatedCount = Math.max(1, Math.round(totalEligible * 0.50))
        break
      case 'percentage_75':
        estimatedCount = Math.max(1, Math.round(totalEligible * 0.75))
        break
      case 'custom_count':
        if (customCount <= 0) {
          errors.push('Custom count must be greater than 0')
        } else if (customCount > totalEligible) {
          errors.push(`Custom count cannot exceed ${totalEligible} eligible records`)
        } else {
          estimatedCount = customCount
        }
        break
      case 'specific_rows':
        if (selectedIds.size === 0) {
          errors.push('Please select at least one row')
        } else if (selectedIds.size > totalEligible) {
          errors.push(`Cannot select more than ${totalEligible} rows`)
        } else {
          estimatedCount = selectedIds.size
        }
        break
    }

    const validationResult = {
      valid: errors.length === 0,
      errors,
      estimatedCount,
      selectedMode,
      totalEligible
    }

    setValidation(validationResult)
    onValidationChange(validationResult)
  }

  const handleModeChange = (mode: string) => {
    setSelectedMode(mode)
    if (mode !== 'custom_count') {
      setCustomCount(1)
    }
    if (mode === 'specific_rows') {
      setPage(1)
    }
  }

  const toggleRecord = (recordId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(recordId)) {
        next.delete(recordId)
      } else {
        next.add(recordId)
      }
      return next
    })
  }

  const handleSearchChange = (value: string) => {
    setSearch(value)
    setPage(1)
  }

  const handleWorkloadSelect = () => {
    if (!validation.valid) return

    const selection = {
      mode: selectedMode,
      count: validation.estimatedCount || 0,
      specificRows: Array.from(selectedIds),
      seed: seed,
      totalEligible: totalEligible
    }

    onWorkloadSelect(selection)
  }

  const getModeDescription = (mode: string) => {
    const modeInfo = workloadModes.find(m => m.value === mode)
    return modeInfo ? modeInfo.description : ''
  }

  const getEstimatedCount = () => {
    if (validation.estimatedCount) {
      return validation.estimatedCount
    }
    return 0
  }

  // Mapped metadata columns worth showing (non-other, excluding review_text/record_id)
  const metadataColumns = Object.keys(fieldMapping).filter(
    h => fieldMapping[h] !== 'other' && fieldMapping[h] !== 'review_text' && fieldMapping[h] !== 'record_id'
  )

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Workload Selection</h3>
      <p>Choose how many records to process for classification.</p>
      
      {/* Eligibility Info */}
      <div style={{ 
        backgroundColor: 'var(--info-soft)', 
        padding: '15px', 
        borderRadius: 'var(--radius-sm)', 
        marginBottom: '20px' 
      }}>
        <strong>Eligible Records:</strong> {totalEligible.toLocaleString()}
        {eligibilityInfo && (
          <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '5px' }}>
            Loaded physical rows: {eligibilityInfo.loaded.toLocaleString()} · 
            Eligible review records: {eligibilityInfo.eligible.toLocaleString()} · 
            Excluded blank rows: {eligibilityInfo.excluded.toLocaleString()}
          </div>
        )}
      </div>

      {/* Mode Selection */}
      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
          Selection Mode:
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
          {workloadModes.map(mode => (
            <button
              key={mode.value}
              onClick={() => handleModeChange(mode.value)}
              style={{ 
                padding: '15px',
                backgroundColor: selectedMode === mode.value ? 'var(--primary)' : 'var(--surface-2)',
                color: selectedMode === mode.value ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>
                {mode.label}
              </div>
              <div style={{ fontSize: '12px', opacity: 0.8 }}>
                {mode.description}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Mode-specific Parameters */}
      {selectedMode === 'custom_count' && (
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Custom Count:
          </label>
          <input
            type="number"
            min="1"
            max={totalEligible}
            value={customCount}
            onChange={(e) => setCustomCount(parseInt(e.target.value) || 1)}
            style={{ 
              width: '200px', 
              padding: '8px', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--radius-sm)' 
            }}
          />
          <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '5px' }}>
            Maximum: {totalEligible} records
          </div>
        </div>
      )}

      {selectedMode === 'specific_rows' && (
        <div style={{ marginBottom: '20px' }}>
          {/* Selection bias warning */}
          <div style={{
            padding: '10px',
            backgroundColor: 'var(--warning-soft)',
            border: '1px solid var(--warning)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '15px',
            fontSize: '13px',
            color: 'var(--warning)'
          }}>
            Manual row selection may introduce selection bias. These records may not
            represent the full dataset, so classification findings and recommendations
            should be interpreted only for the selected rows.
          </div>

          <div style={{ marginBottom: '10px', display: 'flex', gap: '15px', alignItems: 'center' }}>
            <input
              type="text"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search by Record ID or review text..."
              style={{
                flex: 1,
                padding: '8px',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)'
              }}
            />
            <strong>{selectedIds.size} records selected.</strong>
          </div>

          {recordsError && (
            <div style={{ color: 'var(--danger)', marginBottom: '10px' }}>{recordsError}</div>
          )}

          <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--surface-2)' }}>
                  <th style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}></th>
                  <th style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>Record ID</th>
                  <th style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>Source Row</th>
                  <th style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>Review Text</th>
                  {metadataColumns.map(col => (
                    <th key={col} style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recordsLoading ? (
                  <tr><td colSpan={4 + metadataColumns.length} style={{ padding: '15px', textAlign: 'center' }}>Loading records...</td></tr>
                ) : records.length === 0 ? (
                  <tr><td colSpan={4 + metadataColumns.length} style={{ padding: '15px', textAlign: 'center' }}>No eligible records found</td></tr>
                ) : records.map(record => (
                  <tr key={record.record_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px' }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(record.record_id)}
                        onChange={() => toggleRecord(record.record_id)}
                      />
                    </td>
                    <td style={{ padding: '8px', fontFamily: 'monospace' }}>{record.record_id}</td>
                    <td style={{ padding: '8px' }}>{record.source_row}</td>
                    <td style={{ padding: '8px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {record.review_text}
                    </td>
                    {metadataColumns.map(col => (
                      <td key={col} style={{ padding: '8px', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {record.metadata[col] !== undefined ? String(record.metadata[col]) : ''}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div style={{ marginTop: '10px', display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{ padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', cursor: page <= 1 ? 'not-allowed' : 'pointer' }}
            >
              Previous
            </button>
            <span style={{ fontSize: '13px' }}>
              Page {page} of {totalPages} ({recordsTotal.toLocaleString()} eligible records)
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{ padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', cursor: page >= totalPages ? 'not-allowed' : 'pointer' }}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Seed for Reproducibility (not shown for manual specific-rows selection) */}
      {selectedMode !== 'specific_rows' && (
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Random Seed:
          </label>
          <input
            type="number"
            value={seed}
            onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
            style={{ 
              width: '150px', 
              padding: '8px', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--radius-sm)' 
            }}
          />
          <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '5px' }}>
            Used for reproducible random selection
          </div>
        </div>
      )}

      {/* Validation Status */}
      {validation.errors && validation.errors.length > 0 && selectedMode !== 'specific_rows' && (
        <div style={{ 
          padding: '10px', 
          backgroundColor: 'var(--danger-soft)', 
          border: '1px solid var(--danger)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '20px'
        }}>
          <strong style={{ color: 'var(--danger)' }}>Validation Errors:</strong>
          <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px' }}>
            {validation.errors.map((error: string, index: number) => (
              <li key={index} style={{ color: 'var(--danger)' }}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Selection Summary */}
      <div className="card">
        <h4 style={{ margin: '0 0 14px 0' }}>Selection Summary</h4>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '14px'
        }}>
          <div style={{ padding: '14px', backgroundColor: 'var(--surface-2)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
            <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
              {workloadModes.find(m => m.value === selectedMode)?.label}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Mode</div>
          </div>
          <div style={{ padding: '14px', backgroundColor: 'var(--info-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
            <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--info)' }}>
              {getEstimatedCount().toLocaleString()}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
              {selectedMode === 'specific_rows' ? 'Selected' : 'Estimated Count'}
            </div>
          </div>
          <div style={{ padding: '14px', backgroundColor: 'var(--surface-2)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
            <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
              {totalEligible > 0 ? ((getEstimatedCount() / totalEligible) * 100).toFixed(1) : 0}%
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>of Eligible</div>
          </div>
          <div style={{
            padding: '14px',
            backgroundColor: validation.valid ? 'var(--success-soft)' : 'var(--danger-soft)',
            borderRadius: 'var(--radius-sm)',
            textAlign: 'center'
          }}>
            <span className={`chip ${validation.valid ? 'chip-success' : 'chip-danger'}`} style={{ fontSize: '13px' }}>
              {validation.valid ? '✓ Valid' : '✗ Invalid'}
            </span>
            <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '4px' }}>Status</div>
          </div>
        </div>
      </div>

      {/* Action Button */}
      <div style={{ textAlign: 'center' }}>
        <button
          className="btn btn-primary"
          onClick={handleWorkloadSelect}
          disabled={!validation.valid}
          style={{ padding: '12px 28px', fontSize: '15px' }}
        >
          Select Workload
        </button>
      </div>
    </div>
  )
}

export default WorkloadSelector
