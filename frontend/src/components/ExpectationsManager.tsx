import React, { useState, useEffect } from 'react'

interface Expectation {
  id?: string
  record_id: string
  type: string
  expected_value: string
  confidence?: string
  notes?: string
  status?: string
}

interface CategorySet {
  id: string
  name: string
  categories: any[]
}

interface ExpectationsManagerProps {
  sampleRecords: any[]
  classificationMode?: 'defined' | 'undefined'
  categorySet?: CategorySet | null
  onExpectationsComplete: (expectations: any) => void
}

const ExpectationsManager: React.FC<ExpectationsManagerProps> = ({
  sampleRecords,
  classificationMode = 'defined',
  categorySet = null,
  onExpectationsComplete
}) => {
  const isUndefinedMode = classificationMode === 'undefined'
  const [expectations, setExpectations] = useState<Expectation[]>([])
  const [expectationType, setExpectationType] = useState<string>(
    isUndefinedMode ? 'expected_theme' : 'primary_category'
  )
  const [showBulkAdd, setShowBulkAdd] = useState<boolean>(false)
  const [bulkExpectation, setBulkExpectation] = useState<string>('')
  const [bulkType, setBulkType] = useState<string>(
    isUndefinedMode ? 'expected_theme' : 'primary_category'
  )
  const [loading, setLoading] = useState<boolean>(false)

  const definedTypes = [
    { value: 'primary_category', label: 'Primary Category', description: 'Main classification category' },
    { value: 'secondary_category', label: 'Secondary Category', description: 'Additional classification' },
    { value: 'sentiment', label: 'Sentiment', description: 'Positive/negative/neutral' },
    { value: 'confidence', label: 'Confidence', description: 'High/medium/low confidence' },
    { value: 'custom', label: 'Custom', description: 'Custom expectation type' }
  ]

  const undefinedTypes = [
    { value: 'expected_theme', label: 'Expected Theme', description: 'Theme(s) you expect this record to be about' },
    { value: 'sentiment', label: 'Sentiment', description: 'Positive/negative/neutral' },
    { value: 'custom', label: 'Custom', description: 'Custom expectation type' }
  ]

  const expectationTypes = isUndefinedMode ? undefinedTypes : definedTypes

  // Category names for dropdowns in defined mode
  const categoryOptions: string[] = (categorySet?.categories || [])
    .map((c: any) => c.name)
    .filter(Boolean)

  const isCategoryType = (type: string) =>
    type === 'primary_category' || type === 'secondary_category'

  const confidenceLevels = ['high', 'medium', 'low']

  useEffect(() => {
    // Initialize expectations for each record
    if (sampleRecords && sampleRecords.length > 0) {
      const initialExpectations = sampleRecords.map((record, index) => ({
        id: `exp_${index}`,
        record_id: record.id || `record_${index}`,
        type: expectationType,
        expected_value: '',
        confidence: 'medium',
        notes: '',
        status: 'pending'
      }))
      setExpectations(initialExpectations)
    }
  }, [sampleRecords, expectationType])

  const updateExpectation = (index: number, field: keyof Expectation, value: string) => {
    const updatedExpectations = [...expectations]
    updatedExpectations[index] = { ...updatedExpectations[index], [field]: value }
    setExpectations(updatedExpectations)
  }

  const addBulkExpectation = () => {
    if (!bulkExpectation.trim()) return
    
    const values = bulkExpectation.split(',').map(v => v.trim()).filter(v => v)
    
    const updatedExpectations = expectations.map((exp, index) => {
      if (index < values.length) {
        return { ...exp, expected_value: values[index], type: bulkType }
      }
      return exp
    })
    
    setExpectations(updatedExpectations)
    setBulkExpectation('')
    setShowBulkAdd(false)
  }

  const handleSkip = () => {
    onExpectationsComplete({
      expectation_set_id: null,
      expectations: [],
      skipped: true
    })
  }

  const handleComplete = async () => {
    setLoading(true)

    try {
      // Filter out expectations without expected values
      const validExpectations = expectations.filter(exp => exp.expected_value.trim())

      if (validExpectations.length === 0) {
        // Expectations are optional — continue without them
        handleSkip()
        return
      }

      const response = await fetch('/api/sampling/expectations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          sample_id: 'current_sample',
          expectations: validExpectations,
          description: 'User expectations for classification preview'
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        onExpectationsComplete({
          expectation_set_id: data.expectation_set_id,
          expectations: validExpectations,
          summary: data.summary
        })
      } else {
        alert('Failed to save expectations: ' + data.error)
      }
    } catch (error) {
      alert('Error saving expectations: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const getExpectationTypeLabel = (type: string) => {
    const typeInfo = expectationTypes.find(t => t.value === type)
    return typeInfo ? typeInfo.label : type
  }

  const getStatusColor = (status: string) => {
    const colors = {
      'pending': 'var(--warning)',
      'confirmed': 'var(--success)',
      'rejected': 'var(--danger)',
      'partial': 'var(--info)'
    }
    return colors[status as keyof typeof colors] || 'var(--text-2)'
  }

  const getCompletionStats = () => {
    const total = expectations.length
    const completed = expectations.filter(exp => exp.expected_value.trim()).length
    return { total, completed, percentage: total > 0 ? (completed / total) * 100 : 0 }
  }

  const stats = getCompletionStats()

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Expectations Management</h3>
      <p>
        {isUndefinedMode
          ? 'Optionally note the theme(s) you expect each record to be about. These are compared against discovered categories later.'
          : 'Set your expectations for how the records should be classified. These are compared against actual AI classifications later.'}
      </p>
      <div style={{
        padding: '10px',
        backgroundColor: 'var(--warning-soft)',
        border: '1px solid var(--warning)',
        borderRadius: 'var(--radius-sm)',
        marginBottom: '20px',
        fontSize: '13px'
      }}>
        Expectations are optional — you can continue without them. Any you provide are saved for expected-vs-actual comparison.
      </div>
      
      {/* Progress Indicator */}
      <div style={{ 
        backgroundColor: 'var(--info-soft)', 
        padding: '15px', 
        borderRadius: 'var(--radius-sm)', 
        marginBottom: '20px' 
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>Expectation Progress:</strong>
          <span>{stats.completed}/{stats.total} completed ({stats.percentage.toFixed(0)}%)</span>
        </div>
        <div style={{ 
          width: '100%', 
          height: '8px', 
          backgroundColor: 'var(--border)', 
          borderRadius: 'var(--radius-sm)', 
          marginTop: '10px',
          overflow: 'hidden'
        }}>
          <div style={{ 
            width: `${stats.percentage}%`, 
            height: '100%', 
            backgroundColor: 'var(--success)',
            transition: 'width 0.3s ease'
          }} />
        </div>
      </div>

      {/* Expectation Type Selection */}
      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
          Expectation Type:
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
          {expectationTypes.map(type => (
            <button
              key={type.value}
              onClick={() => setExpectationType(type.value)}
              style={{ 
                padding: '12px',
                backgroundColor: expectationType === type.value ? 'var(--primary)' : 'var(--surface-2)',
                color: expectationType === type.value ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: '12px'
              }}
            >
              <div style={{ fontWeight: 'bold', marginBottom: '3px' }}>
                {type.label}
              </div>
              <div style={{ opacity: 0.8 }}>
                {type.description}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Bulk Add */}
      <div style={{ marginBottom: '20px' }}>
        <button
          onClick={() => setShowBulkAdd(!showBulkAdd)}
          style={{
            padding: '8px 16px',
            backgroundColor: 'var(--success)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            marginBottom: '10px'
          }}
        >
          {showBulkAdd ? 'Cancel Bulk Add' : 'Bulk Add Expectations'}
        </button>

        {showBulkAdd && (
          <div style={{
            padding: '15px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--surface-2)'
          }}>
            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                Type:
              </label>
              <select
                value={bulkType}
                onChange={(e) => setBulkType(e.target.value)}
                style={{ padding: '5px', marginRight: '10px' }}
              >
                {expectationTypes.map(type => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                Expected Values (comma-separated):
              </label>
              <textarea
                value={bulkExpectation}
                onChange={(e) => setBulkExpectation(e.target.value)}
                style={{
                  width: '100%',
                  height: '60px',
                  padding: '8px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)'
                }}
                placeholder="value1, value2, value3..."
              />
            </div>
            <button
              onClick={addBulkExpectation}
              style={{
                padding: '8px 16px',
                backgroundColor: 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer'
              }}
            >
              Apply to Records
            </button>
          </div>
        )}
      </div>

      {/* Expectations List */}
      <div style={{ marginBottom: '20px' }}>
        <h4>Record Expectations ({expectations.length} records)</h4>
        <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
          {expectations.map((expectation, index) => {
            const record = sampleRecords[index]
            return (
              <div key={index} style={{
                padding: '15px',
                borderBottom: index < expectations.length - 1 ? '1px solid var(--border)' : 'none',
                backgroundColor: expectation.expected_value.trim() ? 'var(--success-soft)' : 'var(--surface)'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <strong>Record {index + 1}: {expectation.record_id}</strong>
                  <span style={{ 
                    padding: '2px 8px', 
                    backgroundColor: getStatusColor(expectation.status || 'pending'),
                    color: 'white',
                    borderRadius: '12px',
                    fontSize: '10px'
                  }}>
                    {expectation.status || 'pending'}
                  </span>
                </div>
                
                {/* Record Preview */}
                <div style={{ 
                  padding: '8px', 
                  backgroundColor: 'var(--surface-2)', 
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12px',
                  marginBottom: '10px',
                  maxHeight: '60px',
                  overflow: 'hidden'
                }}>
                  {record?.review_text ? 
                    (record.review_text.length > 100 ? 
                      record.review_text.substring(0, 100) + '...' : 
                      record.review_text) : 
                    'No review text available'}
                </div>
                
                {/* Expectation Fields */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 'bold' }}>
                      {isUndefinedMode ? 'Expected Theme(s):' : 'Expected Value:'}
                    </label>
                    {!isUndefinedMode && isCategoryType(expectation.type) && categoryOptions.length > 0 ? (
                      <select
                        value={expectation.expected_value}
                        onChange={(e) => updateExpectation(index, 'expected_value', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '4px',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '12px'
                        }}
                      >
                        <option value="">Select category...</option>
                        {categoryOptions.map(name => (
                          <option key={name} value={name}>{name}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={expectation.expected_value}
                        onChange={(e) => updateExpectation(index, 'expected_value', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '4px',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '12px'
                        }}
                        placeholder={isUndefinedMode ? 'e.g. search, syncing, storage...' : 'Enter expectation...'}
                      />
                    )}
                  </div>
                  
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 'bold' }}>Confidence:</label>
                    <select
                      value={expectation.confidence || 'medium'}
                      onChange={(e) => updateExpectation(index, 'confidence', e.target.value)}
                      style={{
                        width: '100%',
                        padding: '4px',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px'
                      }}
                    >
                      {confidenceLevels.map(level => (
                        <option key={level} value={level}>{level}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 'bold' }}>Type:</label>
                    <select
                      value={expectation.type}
                      onChange={(e) => updateExpectation(index, 'type', e.target.value)}
                      style={{
                        width: '100%',
                        padding: '4px',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px'
                      }}
                    >
                      {expectationTypes.map(type => (
                        <option key={type.value} value={type.value}>{type.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                
                {/* Notes */}
                <div style={{ marginTop: '10px' }}>
                  <label style={{ fontSize: '11px', fontWeight: 'bold' }}>Notes (optional):</label>
                  <input
                    type="text"
                    value={expectation.notes || ''}
                    onChange={(e) => updateExpectation(index, 'notes', e.target.value)}
                    style={{
                      width: '100%',
                      padding: '4px',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '12px'
                    }}
                    placeholder="Additional notes..."
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ textAlign: 'center', display: 'flex', gap: '12px', justifyContent: 'center' }}>
        <button
          onClick={handleComplete}
          disabled={loading}
          style={{
            padding: '12px 24px',
            backgroundColor: !loading ? 'var(--success)' : 'var(--border)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: !loading ? 'pointer' : 'not-allowed',
            fontSize: '16px'
          }}
        >
          {loading ? 'Saving Expectations...' : `Save Expectations (${stats.completed}/${stats.total})`}
        </button>
        <button
          onClick={handleSkip}
          disabled={loading}
          style={{
            padding: '12px 24px',
            backgroundColor: 'var(--surface-2)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          Continue without Expectations
        </button>
      </div>
    </div>
  )
}

export default ExpectationsManager
