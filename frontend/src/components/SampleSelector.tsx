import React, { useState, useEffect } from 'react'

interface WorkloadSelection {
  mode: string
  count: number
  specificRows: string[]
  seed: number
  totalEligible: number
}

interface SampleSelectorProps {
  fileId?: string
  fieldMapping?: { [key: string]: string }
  useColumnIds?: boolean
  workloadSelection?: WorkloadSelection | null
  totalEligible?: number
  onSampleSelect: (sample: any) => void
  onValidationChange: (validation: any) => void
}

const SampleSelector: React.FC<SampleSelectorProps> = ({
  fileId,
  fieldMapping = {},
  useColumnIds = true,
  workloadSelection = null,
  totalEligible = 0,
  onSampleSelect,
  onValidationChange
}) => {
  const [samplingMethod, setSamplingMethod] = useState<string>('random')
  const [sampleSize, setSampleSize] = useState<number>(10)
  const [stratifyField, setStratifyField] = useState<string>('')
  const [seed, setSeed] = useState<number>(42)
  const [sampleResult, setSampleResult] = useState<any>(null)
  const [validation, setValidation] = useState<any>({})
  const [loading, setLoading] = useState<boolean>(false)

  // Effective sampling pool: the stored snapshot's eligible records,
  // restricted to the selected workload when it is smaller.
  const availableCount = (() => {
    if (!fileId) return 0
    if (!workloadSelection || workloadSelection.mode === 'all_eligible') {
      return totalEligible
    }
    if (workloadSelection.mode === 'specific_rows') {
      return Math.min(workloadSelection.specificRows.length, totalEligible)
    }
    return Math.min(workloadSelection.count, totalEligible)
  })()

  const samplingMethods = [
    { value: 'random', label: 'Random Sampling', description: 'Select random records' },
    { value: 'stratified', label: 'Stratified Sampling', description: 'Sample by field values' },
    { value: 'systematic', label: 'Systematic Sampling', description: 'Every nth record' },
    { value: 'cluster', label: 'Cluster Sampling', description: 'Group similar records' }
  ]

  useEffect(() => {
    validateSelection()
  }, [samplingMethod, sampleSize, stratifyField, availableCount])

  const validateSelection = () => {
    const errors = []
    const warnings = []

    if (!fileId) {
      errors.push('No dataset selected. Upload a file first.')
    } else if (availableCount === 0) {
      errors.push('No eligible records available for sampling')
    } else {
      if (sampleSize < 5) {
        errors.push('Sample size must be at least 5')
      }
      if (sampleSize > availableCount) {
        errors.push(`Sample size cannot exceed ${availableCount} records`)
      }
      if (samplingMethod === 'stratified' && !stratifyField) {
        errors.push('Stratified sampling requires a field to stratify by')
      }
      if (sampleSize > 50) {
        warnings.push('Large sample sizes may increase processing time')
      }
    }

    const validationResult = {
      valid: errors.length === 0,
      errors,
      warnings,
      sampleSize: Math.min(sampleSize, availableCount),
      totalRecords: availableCount
    }

    setValidation(validationResult)
    onValidationChange(validationResult)
  }

  const handleSampleSelect = async () => {
    if (!validation.valid) return

    setLoading(true)

    try {
      const response = await fetch('/api/sampling/select', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          file_id: fileId,
          field_mapping: fieldMapping,
          use_column_ids: useColumnIds,
          workload: workloadSelection,
          method: samplingMethod,
          sample_size: sampleSize,
          stratify_field: stratifyField || undefined,
          seed: seed
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        setSampleResult(data.sample_result)
        onSampleSelect(data.sample_result)
      } else {
        alert('Sample selection failed: ' + data.error)
      }
    } catch (error) {
      alert('Error selecting sample: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const getRecommendedSize = () => {
    if (availableCount === 0) return 10

    if (availableCount <= 10) return availableCount
    if (availableCount <= 100) return Math.max(10, Math.floor(availableCount * 0.2))
    if (availableCount <= 1000) return Math.max(20, Math.floor(availableCount * 0.1))
    return Math.min(50, Math.floor(availableCount * 0.05))
  }

  const getStratifyFields = () => {
    // Stratify fields are the mapped metadata columns (review text and
    // record IDs are not meaningful grouping fields).
    return Object.keys(fieldMapping).filter(
      h => fieldMapping[h] !== 'other' && fieldMapping[h] !== 'review_text' && fieldMapping[h] !== 'record_id'
    )
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Sample Selection</h3>
      <p>Select a representative sample for classification preview.</p>
      
      {/* Dataset Info */}
      <div style={{ 
        backgroundColor: 'var(--info-soft)', 
        padding: '15px', 
        borderRadius: 'var(--radius-sm)', 
        marginBottom: '20px' 
      }}>
        <strong>Dataset:</strong> {availableCount.toLocaleString()} records available
        {workloadSelection && workloadSelection.mode !== 'all_eligible' && totalEligible > availableCount && (
          <span style={{ fontSize: '12px', color: 'var(--text-2)', marginLeft: '10px' }}>
            (restricted to {workloadSelection.mode.replace(/_/g, ' ')} workload of {totalEligible.toLocaleString()} eligible)
          </span>
        )}
      </div>

      {/* Sampling Method */}
      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
          Sampling Method:
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
          {samplingMethods.map(method => (
            <button
              key={method.value}
              onClick={() => setSamplingMethod(method.value)}
              style={{ 
                padding: '15px',
                backgroundColor: samplingMethod === method.value ? 'var(--primary)' : 'var(--surface-2)',
                color: samplingMethod === method.value ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>
                {method.label}
              </div>
              <div style={{ fontSize: '12px', opacity: 0.8 }}>
                {method.description}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Sample Size */}
      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          Sample Size:
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input
            type="number"
            min="5"
            max={availableCount || 50}
            value={sampleSize}
            onChange={(e) => setSampleSize(parseInt(e.target.value) || 10)}
            style={{ 
              width: '120px', 
              padding: '8px', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--radius-sm)' 
            }}
          />
          <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>
            (Recommended: {getRecommendedSize()})
          </span>
        </div>
      </div>

      {/* Stratify Field (for stratified sampling) */}
      {samplingMethod === 'stratified' && (
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Stratify By Field:
          </label>
          <select
            value={stratifyField}
            onChange={(e) => setStratifyField(e.target.value)}
            style={{ 
              width: '200px', 
              padding: '8px', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--radius-sm)' 
            }}
          >
            <option value="">Select field...</option>
            {getStratifyFields().map(field => (
              <option key={field} value={field}>{field}</option>
            ))}
          </select>
        </div>
      )}

      {/* Random Seed */}
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
          Used for reproducible sample selection
        </div>
      </div>

      {/* Validation Status */}
      {validation.errors && validation.errors.length > 0 && (
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

      {validation.warnings && validation.warnings.length > 0 && (
        <div style={{ 
          padding: '10px', 
          backgroundColor: 'var(--warning-soft)', 
          border: '1px solid var(--warning)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '20px'
        }}>
          <strong style={{ color: 'var(--warning)' }}>Warnings:</strong>
          <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px' }}>
            {validation.warnings.map((warning: string, index: number) => (
              <li key={index} style={{ color: 'var(--warning)' }}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Sample Summary */}
      {sampleResult && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: 'var(--success-soft)', 
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--success)',
          marginBottom: '20px'
        }}>
          <h4>Sample Selected</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
            <div>
              <strong>Method:</strong> {sampleResult.sampling_method}
            </div>
            <div>
              <strong>Size:</strong> {sampleResult.sample_size}/{sampleResult.total_records}
            </div>
            <div>
              <strong>Seed:</strong> {sampleResult.seed}
            </div>
            <div>
              <strong>Text Length:</strong> {sampleResult.sample_analysis?.text_length?.mean?.toFixed(0) || 'N/A'} avg chars
            </div>
          </div>
          
          {sampleResult.sample_analysis?.rating_distribution && (
            <div style={{ marginTop: '15px' }}>
              <strong>Rating Distribution:</strong>
              <div style={{ fontSize: '12px', marginTop: '5px' }}>
                Min: {sampleResult.sample_analysis.rating_distribution.min}, 
                Max: {sampleResult.sample_analysis.rating_distribution.max}, 
                Mean: {sampleResult.sample_analysis.rating_distribution.mean?.toFixed(2)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action Button */}
      <div style={{ textAlign: 'center' }}>
        <button
          onClick={handleSampleSelect}
          disabled={!validation.valid || loading}
          style={{ 
            padding: '12px 24px',
            backgroundColor: validation.valid && !loading ? 'var(--success)' : 'var(--border)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: validation.valid && !loading ? 'pointer' : 'not-allowed',
            fontSize: '16px'
          }}
        >
          {loading ? 'Selecting Sample...' : 'Select Sample'}
        </button>
      </div>
    </div>
  )
}

export default SampleSelector
