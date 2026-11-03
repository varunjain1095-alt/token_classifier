import React, { useState } from 'react'

interface UndefinedClassificationConfigProps {
  onConfigSelect: (config: any) => void
}

const OUTPUT_FIELD_OPTIONS = [
  { value: 'primary_category', label: 'Primary category', alwaysOn: true },
  { value: 'secondary_categories', label: 'Secondary categories (multi-label)', alwaysOn: false },
  { value: 'supporting_evidence', label: 'Supporting evidence quote', alwaysOn: false },
  { value: 'classification_state', label: 'Classification state (matched / unmatched / ambiguous)', alwaysOn: false },
  { value: 'confidence', label: 'Model-reported confidence', alwaysOn: false },
  { value: 'explanation', label: 'Explanation / reasoning', alwaysOn: false }
]

const UndefinedClassificationConfig: React.FC<UndefinedClassificationConfigProps> = ({ onConfigSelect }) => {
  const [objective, setObjective] = useState<string>('')
  const [labelMode, setLabelMode] = useState<string>('single_label')
  const [outputFields, setOutputFields] = useState<Set<string>>(new Set(['primary_category', 'supporting_evidence']))
  const [themeGuidance, setThemeGuidance] = useState<string>('')
  const [saving, setSaving] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [savedConfig, setSavedConfig] = useState<any>(null)

  const toggleOutputField = (field: string) => {
    setOutputFields(prev => {
      const next = new Set(prev)
      if (next.has(field)) {
        next.delete(field)
      } else {
        next.add(field)
      }
      return next
    })
  }

  const canSave = objective.trim().length > 0 && outputFields.size > 0 && !saving

  const saveConfig = async () => {
    if (!canSave) return
    setSaving(true)
    setError('')
    try {
      const response = await fetch('/api/configuration/experiment-configs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          name: `Undefined Classification - ${objective.trim().slice(0, 50)}`,
          description: 'Categories will be proposed as drafts by the preview model.',
          config: {
            classification_type: 'undefined',
            input_fields: ['review_text'],
            output_format: 'json',
            max_tokens: 300,
            temperature: 0.2,
            batch_size: 10,
            objective: objective.trim(),
            label_mode: labelMode,
            output_fields: Array.from(outputFields),
            theme_guidance: themeGuidance.trim() || undefined,
            category_mode: 'discovery',
            draft_categories: true
          }
        })
      })
      const data = await response.json()
      if (data.success) {
        setSavedConfig(data.config)
        onConfigSelect(data.config)
      } else {
        setError(data.detail || data.error || 'Failed to create configuration')
      }
    } catch (e) {
      setError('Failed to create configuration')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Undefined Classification Configuration</h3>

      {/* Explanation */}
      <div style={{
        padding: '12px',
        backgroundColor: 'var(--info-soft)',
        borderRadius: 'var(--radius-sm)',
        marginBottom: '20px',
        fontSize: '13px'
      }}>
        No category set is required. The preview model will analyse the selected
        sample and propose draft categories later. Proposed categories remain
        drafts. You will be able to edit, merge, split, delete or approve them
        before they become a versioned category set.
      </div>

      {/* Objective */}
      <div style={{ marginBottom: '15px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          Describe the problem you're investigating: <span style={{ fontWeight: 'normal', color: 'var(--text-2)' }}>(required)</span>
        </label>
        <textarea
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="e.g., Users report Google Photos search is unreliable. I want to find which friction points recur most: failing searches, sync issues, or missing features."
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            height: '70px'
          }}
        />
      </div>

      {/* Label mode */}
      <div style={{ marginBottom: '15px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          Label Mode:
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px' }}>
          <input
            type="radio"
            name="label_mode"
            checked={labelMode === 'single_label'}
            onChange={() => {
              setLabelMode('single_label')
              setOutputFields(prev => {
                const next = new Set(prev)
                next.delete('secondary_categories')
                return next
              })
            }}
          />
          Single-label: each review gets at most one category
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="radio"
            name="label_mode"
            checked={labelMode === 'multi_label'}
            onChange={() => setLabelMode('multi_label')}
          />
          Multi-label: a review may belong to several categories
        </label>
      </div>

      {/* Desired output fields */}
      <div style={{ marginBottom: '15px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          Desired Output Fields:
        </label>
        {OUTPUT_FIELD_OPTIONS.map(opt => {
          const disabled = opt.alwaysOn || (opt.value === 'secondary_categories' && labelMode === 'single_label')
          return (
            <label key={opt.value} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '4px',
              color: disabled ? 'var(--text-2)' : 'var(--text)'
            }}>
              <input
                type="checkbox"
                checked={opt.alwaysOn || outputFields.has(opt.value)}
                disabled={disabled}
                onChange={() => toggleOutputField(opt.value)}
              />
              {opt.label}
              {opt.alwaysOn && <span style={{ fontSize: '12px' }}>(always included)</span>}
            </label>
          )
        })}
      </div>

      {/* Optional theme guidance */}
      <div style={{ marginBottom: '15px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          Themes you suspect exist <span style={{ fontWeight: 'normal', color: 'var(--text-2)' }}>(optional)</span>:
        </label>
        <textarea
          value={themeGuidance}
          onChange={(e) => setThemeGuidance(e.target.value)}
          placeholder="e.g., I expect themes around sync reliability, storage limits and sharing features"
          style={{
            width: '100%',
            padding: '8px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            height: '60px'
          }}
        />
      </div>

      {error && (
        <div style={{ color: 'var(--danger)', marginBottom: '10px' }}>{error}</div>
      )}

      {savedConfig && (
        <div style={{
          padding: '12px',
          backgroundColor: 'var(--success-soft)',
          border: '1px solid var(--success)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '15px',
          fontSize: '13px'
        }}>
          <strong>Configuration saved:</strong> {savedConfig.name} (v{savedConfig.version})
        </div>
      )}

      <button
        onClick={saveConfig}
        disabled={!canSave}
        style={{
          padding: '10px 20px',
          backgroundColor: canSave ? 'var(--success)' : 'var(--border)',
          color: 'white',
          border: 'none',
          borderRadius: 'var(--radius-sm)',
          cursor: canSave ? 'pointer' : 'not-allowed'
        }}
      >
        {saving ? 'Saving...' : 'Save & Continue'}
      </button>
    </div>
  )
}

export default UndefinedClassificationConfig
