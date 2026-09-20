import React, { useState, useEffect } from 'react'

interface ExperimentConfig {
  id: string
  name: string
  description: string
  config: {
    classification_type: string
    input_fields: string[]
    output_format: string
    max_tokens: number
    temperature: number
    batch_size?: number
    category_set_id?: string
    system_prompt?: string
  }
  version: number
  is_active: boolean
}

interface ExperimentConfigProps {
  categorySetId?: string
  onConfigSelect: (config: ExperimentConfig) => void
}

const ExperimentConfig: React.FC<ExperimentConfigProps> = ({ categorySetId, onConfigSelect }) => {
  const [configs, setConfigs] = useState<ExperimentConfig[]>([])
  const [selectedConfig, setSelectedConfig] = useState<ExperimentConfig | null>(null)
  const [showCreateForm, setShowCreateForm] = useState<boolean>(false)
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    classification_type: 'sentiment',
    input_fields: ['review_text'],
    output_format: 'json',
    max_tokens: 150,
    temperature: 0.1,
    batch_size: 10,
    category_set_id: categorySetId || '',
    system_prompt: 'Classify the sentiment of the following review as positive, negative, or neutral.'
  })

  useEffect(() => {
    loadConfigs()
  }, [])

  useEffect(() => {
    if (categorySetId) {
      setFormData(prev => ({ ...prev, category_set_id: categorySetId }))
    }
  }, [categorySetId])

  const loadConfigs = async () => {
    try {
      const response = await fetch('/api/configuration/experiment-configs')
      const data = await response.json()
      if (data.success) {
        setConfigs(data.configs)
      }
    } catch (error) {
      console.error('Failed to load experiment configs:', error)
    }
  }

  const createConfig = async () => {
    try {
      const response = await fetch('/api/configuration/experiment-configs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description,
          config: {
            classification_type: formData.classification_type,
            input_fields: formData.input_fields,
            output_format: formData.output_format,
            max_tokens: formData.max_tokens,
            temperature: formData.temperature,
            batch_size: formData.batch_size,
            category_set_id: formData.category_set_id || undefined,
            system_prompt: formData.system_prompt
          }
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        setShowCreateForm(false)
        resetForm()
        loadConfigs()
      } else {
        alert('Failed to create configuration: ' + data.error)
      }
    } catch (error) {
      alert('Error creating configuration: ' + error)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      classification_type: 'sentiment',
      input_fields: ['review_text'],
      output_format: 'json',
      max_tokens: 150,
      temperature: 0.1,
      batch_size: 10,
      category_set_id: categorySetId || '',
      system_prompt: 'Classify the sentiment of the following review as positive, negative, or neutral.'
    })
  }

  const selectConfig = (config: ExperimentConfig) => {
    setSelectedConfig(config)
    onConfigSelect(config)
  }

  const getClassificationTypeLabel = (type: string) => {
    const labels = {
      'sentiment': 'Sentiment Analysis',
      'topic': 'Topic Classification',
      'category': 'Category Classification',
      'custom': 'Custom Classification',
      'undefined': 'Undefined Classification'
    }
    return labels[type as keyof typeof labels] || type
  }

  const getOutputFormatLabel = (format: string) => {
    const labels = {
      'json': 'JSON Object',
      'text': 'Plain Text',
      'structured': 'Structured Data'
    }
    return labels[format as keyof typeof labels] || format
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Experiment Configuration</h3>
      
      {/* Configuration List */}
      <div style={{ marginBottom: '30px' }}>
        <h4>Configurations</h4>
        {configs.length === 0 ? (
          <p>No experiment configurations found. Create your first configuration below.</p>
        ) : (
          <div style={{ display: 'grid', gap: '10px' }}>
            {configs.map((config) => (
              <div
                key={config.id}
                onClick={() => selectConfig(config)}
                style={{
                  padding: '15px',
                  border: selectedConfig?.id === config.id ? '2px solid var(--primary)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  backgroundColor: selectedConfig?.id === config.id ? 'var(--info-soft)' : 'var(--surface-2)'
                }}
              >
                <div style={{ fontWeight: 'bold' }}>{config.name}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                  {getClassificationTypeLabel(config.config.classification_type)} • 
                  Version {config.version} • 
                  {config.config.max_tokens} tokens
                </div>
                {config.description && (
                  <div style={{ fontSize: '12px', marginTop: '5px' }}>{config.description}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create New Configuration */}
      <div style={{ marginBottom: '30px' }}>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          style={{
            padding: '10px 20px',
            backgroundColor: 'var(--success)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            marginBottom: '15px'
          }}
        >
          {showCreateForm ? 'Cancel' : 'Create New Configuration'}
        </button>

        {showCreateForm && (
          <div style={{
            padding: '20px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--surface-2)'
          }}>
            <h4>Create Experiment Configuration</h4>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  Name:
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)'
                  }}
                  placeholder="e.g., Sentiment Analysis v1"
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  Classification Type:
                </label>
                <select
                  value={formData.classification_type}
                  onChange={(e) => setFormData(prev => ({ ...prev, classification_type: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)'
                  }}
                >
                  <option value="sentiment">Sentiment Analysis</option>
                  <option value="topic">Topic Classification</option>
                  <option value="category">Category Classification</option>
                  <option value="custom">Custom Classification</option>
                </select>
              </div>
            </div>

            <div style={{ marginTop: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                Description:
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  height: '60px'
                }}
                placeholder="Optional description..."
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px', marginTop: '15px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  Max Tokens:
                </label>
                <input
                  type="number"
                  value={formData.max_tokens}
                  onChange={(e) => setFormData(prev => ({ ...prev, max_tokens: parseInt(e.target.value) || 150 }))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)'
                  }}
                  min="1"
                  max="4000"
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  Temperature:
                </label>
                <input
                  type="number"
                  value={formData.temperature}
                  onChange={(e) => setFormData(prev => ({ ...prev, temperature: parseFloat(e.target.value) || 0.1 }))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)'
                  }}
                  min="0"
                  max="2"
                  step="0.1"
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  Batch Size:
                </label>
                <input
                  type="number"
                  value={formData.batch_size}
                  onChange={(e) => setFormData(prev => ({ ...prev, batch_size: parseInt(e.target.value) || 10 }))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)'
                  }}
                  min="1"
                  max="100"
                />
              </div>
            </div>

            <div style={{ marginTop: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                Output Format:
              </label>
              <select
                value={formData.output_format}
                onChange={(e) => setFormData(prev => ({ ...prev, output_format: e.target.value }))}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)'
                }}
              >
                <option value="json">JSON Object</option>
                <option value="text">Plain Text</option>
                <option value="structured">Structured Data</option>
              </select>
            </div>

            <div style={{ marginTop: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                System Prompt:
              </label>
              <textarea
                value={formData.system_prompt}
                onChange={(e) => setFormData(prev => ({ ...prev, system_prompt: e.target.value }))}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  height: '80px'
                }}
                placeholder="System prompt for the AI model..."
              />
            </div>

            {categorySetId && (
              <div style={{ marginTop: '15px', padding: '10px', backgroundColor: 'var(--success-soft)', borderRadius: 'var(--radius-sm)' }}>
                <strong>Using Category Set:</strong> {categorySetId}
              </div>
            )}

            <button
              onClick={createConfig}
              disabled={!formData.name.trim()}
              style={{
                padding: '10px 20px',
                backgroundColor: formData.name.trim() ? 'var(--success)' : 'var(--border)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: formData.name.trim() ? 'pointer' : 'not-allowed',
                marginTop: '15px'
              }}
            >
              Create Configuration
            </button>
          </div>
        )}
      </div>

      {/* Selected Configuration Details */}
      {selectedConfig && (
        <div style={{
          padding: '20px',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: 'var(--success-soft)'
        }}>
          <h4>Selected: {selectedConfig.name}</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
            <div>
              <p><strong>Version:</strong> {selectedConfig.version}</p>
              <p><strong>Type:</strong> {getClassificationTypeLabel(selectedConfig.config.classification_type)}</p>
              <p><strong>Output:</strong> {getOutputFormatLabel(selectedConfig.config.output_format)}</p>
            </div>
            <div>
              <p><strong>Max Tokens:</strong> {selectedConfig.config.max_tokens}</p>
              <p><strong>Temperature:</strong> {selectedConfig.config.temperature}</p>
              <p><strong>Batch Size:</strong> {selectedConfig.config.batch_size || 'Default'}</p>
            </div>
          </div>
          {selectedConfig.description && (
            <p><strong>Description:</strong> {selectedConfig.description}</p>
          )}
          {selectedConfig.config.system_prompt && (
            <div>
              <strong>System Prompt:</strong>
              <div style={{ 
                padding: '10px', 
                backgroundColor: 'var(--surface-2)', 
                borderRadius: 'var(--radius-sm)', 
                marginTop: '5px',
                fontSize: '12px',
                fontFamily: 'monospace'
              }}>
                {selectedConfig.config.system_prompt}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ExperimentConfig
