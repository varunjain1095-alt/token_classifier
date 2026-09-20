import React, { useState, useEffect, useRef } from 'react'

interface DiscoveredCategory {
  id: string
  name: string
  type: string
  confidence: number
  description: string
  keywords: string[]
  position: number
}

interface CategoryDiscoveryProps {
  sampleRecords: any[]
  onDiscoveryComplete: (discovery: any) => void
}

const CategoryDiscovery: React.FC<CategoryDiscoveryProps> = ({ 
  sampleRecords, 
  onDiscoveryComplete 
}) => {
  const [discoveryMethod, setDiscoveryMethod] = useState<string>('ai_analysis')
  const [discoveryStatus, setDiscoveryStatus] = useState<string>('idle')
  const [discoveredCategories, setDiscoveredCategories] = useState<DiscoveredCategory[]>([])
  const [discoveryResults, setDiscoveryResults] = useState<any>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [editingCategory, setEditingCategory] = useState<string | null>(null)
  const [newCategoryName, setNewCategoryName] = useState<string>('')
  const startedRef = useRef<boolean>(false)

  const discoveryMethods = [
    { value: 'ai_analysis', label: 'AI Analysis', description: 'Use AI to discover categories' },
    { value: 'clustering', label: 'Clustering', description: 'Group similar reviews' },
    { value: 'hybrid', label: 'Hybrid', description: 'Combine AI and clustering' }
  ]

  useEffect(() => {
    // Auto-start discovery once per mount — re-renders or state restores
    // must not retrigger the request.
    if (!startedRef.current && sampleRecords && sampleRecords.length > 0) {
      startedRef.current = true
      startDiscovery()
    }
  }, [sampleRecords])

  const startDiscovery = async () => {
    setLoading(true)
    setError(null)
    setDiscoveryStatus('analyzing')

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 120000)

    try {
      const response = await fetch('/api/categories/discover', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
        body: JSON.stringify({
          sample_records: sampleRecords,
          method: discoveryMethod,
          user_id: 'current_user'
        }),
      })

      const data = await response.json()

      if (data.success) {
        setDiscoveryResults(data.discovery)
        setDiscoveredCategories(data.discovery.discovered_categories || [])
        setDiscoveryStatus('completed')
        onDiscoveryComplete(data.discovery)
      } else {
        setError(data.error || data.detail || 'Category discovery failed')
        setDiscoveryStatus('failed')
      }
    } catch (error: any) {
      setError(error?.name === 'AbortError'
        ? 'Category discovery timed out after 2 minutes — please retry.'
        : 'Category discovery failed: ' + error)
      setDiscoveryStatus('failed')
    } finally {
      clearTimeout(timer)
      setLoading(false)
    }
  }

  const refineCategory = async (categoryId: string, refinementType: string, data: any) => {
    try {
      const response = await fetch(`/api/categories/refine/${discoveryResults.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: refinementType,
          category_id: categoryId,
          ...data
        }),
      })
      
      const result = await response.json()
      if (result.success) {
        setDiscoveredCategories(result.discovery.discovered_categories || [])
        setDiscoveryResults(result.discovery)
      }
    } catch (error) {
      console.error('Category refinement failed:', error)
    }
  }

  const renameCategory = (categoryId: string, newName: string) => {
    if (newName.trim()) {
      refineCategory(categoryId, 'rename', { new_name: newName })
      setEditingCategory(null)
      setNewCategoryName('')
    }
  }

  const deleteCategory = (categoryId: string) => {
    if (confirm('Are you sure you want to delete this category?')) {
      refineCategory(categoryId, 'delete', {})
    }
  }

  const addCategory = () => {
    const newCategory = {
      name: 'New Category',
      type: 'user_added',
      confidence: 0.9,
      description: 'User-added category',
      keywords: []
    }
    
    // Add to local state first
    const updatedCategories = [...discoveredCategories, newCategory]
    setDiscoveredCategories(updatedCategories)
    
    // Then refine on backend
    refineCategory('', 'add', { category: newCategory })
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'var(--success)'
    if (confidence >= 0.6) return 'var(--warning)'
    return 'var(--danger)'
  }

  const getTypeColor = (type: string) => {
    const colors = {
      'ai_discovered': 'var(--info-soft)',
      'discovered': 'var(--primary-soft)',
      'user_added': 'var(--success-soft)'
    }
    return colors[type as keyof typeof colors] || 'var(--surface-2)'
  }

  const getStatusColor = (status: string) => {
    const colors = {
      'idle': 'var(--text-2)',
      'analyzing': 'var(--warning)',
      'completed': 'var(--success)',
      'failed': 'var(--danger)'
    }
    return colors[status as keyof typeof colors] || 'var(--text-2)'
  }

  if (loading || discoveryStatus === 'analyzing') {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <div style={{ fontSize: '18px', marginBottom: '10px' }}>🔍</div>
        <div>Discovering categories in your data...</div>
        <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '10px' }}>
          Analyzing {sampleRecords?.length || 0} records using {discoveryMethod.replace('_', ' ')}
        </div>
      </div>
    )
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Category Discovery</h3>
      <p>Automatically discover meaningful categories from your review data.</p>
      
      {/* Discovery Method Selection */}
      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
          Discovery Method:
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
          {discoveryMethods.map(method => (
            <button
              key={method.value}
              onClick={() => setDiscoveryMethod(method.value)}
              style={{ 
                padding: '12px',
                backgroundColor: discoveryMethod === method.value ? 'var(--primary)' : 'var(--surface-2)',
                color: discoveryMethod === method.value ? 'white' : 'var(--text)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: '12px'
              }}
            >
              <div style={{ fontWeight: 'bold', marginBottom: '3px' }}>
                {method.label}
              </div>
              <div style={{ opacity: 0.8 }}>
                {method.description}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Discovery Status */}
      <div style={{ 
        padding: '15px', 
        backgroundColor: 'var(--surface-2)', 
        borderRadius: 'var(--radius-sm)',
        marginBottom: '20px',
        textAlign: 'center'
      }}>
        <div style={{ 
          display: 'inline-block',
          padding: '8px 16px',
          backgroundColor: getStatusColor(discoveryStatus),
          color: 'white',
          borderRadius: '20px',
          fontWeight: 'bold'
        }}>
          Status: {discoveryStatus.toUpperCase()}
        </div>
        {discoveryStatus === 'completed' && (
          <div style={{ marginTop: '10px', fontSize: '14px' }}>
            Discovered {discoveredCategories.length} categories
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div style={{ 
          padding: '15px', 
          backgroundColor: 'var(--danger-soft)', 
          border: '1px solid var(--danger)',
          borderRadius: 'var(--radius-sm)',
          color: 'var(--danger)',
          marginBottom: '20px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Discovered Categories */}
      {discoveredCategories.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
            <h4>Discovered Categories ({discoveredCategories.length})</h4>
            <button
              className="btn btn-primary"
              onClick={addCategory}
              style={{ padding: '8px 16px' }}
            >
              Add Category
            </button>
          </div>
          
          <div style={{ display: 'grid', gap: '15px' }}>
            {discoveredCategories
              .sort((a, b) => a.position - b.position)
              .map((category, index) => (
                <div key={category.id} style={{
                  padding: '15px',
                  backgroundColor: getTypeColor(category.type),
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                    <div style={{ flex: 1 }}>
                      {editingCategory === category.id ? (
                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                          <input
                            type="text"
                            value={newCategoryName}
                            onChange={(e) => setNewCategoryName(e.target.value)}
                            placeholder={category.name}
                            style={{
                              flex: 1,
                              padding: '5px',
                              border: '1px solid var(--border)',
                              borderRadius: 'var(--radius-sm)'
                            }}
                          />
                          <button
                            onClick={() => renameCategory(category.id, newCategoryName)}
                            style={{
                              padding: '5px 10px',
                              backgroundColor: 'var(--success)',
                              color: 'white',
                              border: 'none',
                              borderRadius: 'var(--radius-sm)',
                              cursor: 'pointer'
                            }}
                          >
                            Save
                          </button>
                          <button
                            onClick={() => {
                              setEditingCategory(null)
                              setNewCategoryName('')
                            }}
                            style={{
                              padding: '5px 10px',
                              backgroundColor: 'var(--danger)',
                              color: 'white',
                              border: 'none',
                              borderRadius: 'var(--radius-sm)',
                              cursor: 'pointer'
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <h5 style={{ margin: 0, fontSize: '16px' }}>{category.name}</h5>
                          <div style={{ display: 'flex', gap: '5px' }}>
                            <button
                              onClick={() => {
                                setEditingCategory(category.id)
                                setNewCategoryName(category.name)
                              }}
                              style={{
                                padding: '3px 8px',
                                backgroundColor: 'var(--primary)',
                                color: 'white',
                                border: 'none',
                                borderRadius: 'var(--radius-sm)',
                                cursor: 'pointer',
                                fontSize: '11px'
                              }}
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteCategory(category.id)}
                              style={{
                                padding: '3px 8px',
                                backgroundColor: 'var(--danger)',
                                color: 'white',
                                border: 'none',
                                borderRadius: 'var(--radius-sm)',
                                cursor: 'pointer',
                                fontSize: '11px'
                              }}
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                    
                    <div style={{ marginLeft: '15px', textAlign: 'right' }}>
                      <div style={{ 
                        padding: '4px 8px', 
                        backgroundColor: getConfidenceColor(category.confidence),
                        color: 'white',
                        borderRadius: '12px',
                        fontSize: '11px',
                        fontWeight: 'bold'
                      }}>
                        {(category.confidence * 100).toFixed(0)}%
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-2)', marginTop: '2px' }}>
                        {category.type.replace('_', ' ')}
                      </div>
                    </div>
                  </div>
                  
                  {category.description && (
                    <div style={{ fontSize: '14px', color: 'var(--text-2)', marginBottom: '10px' }}>
                      {category.description}
                    </div>
                  )}
                  
                  {category.keywords && category.keywords.length > 0 && (
                    <div style={{ marginTop: '10px' }}>
                      <strong style={{ fontSize: '12px' }}>Keywords:</strong>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '5px' }}>
                        {category.keywords.slice(0, 8).map((keyword, i) => (
                          <span key={i} style={{
                            padding: '2px 6px',
                            backgroundColor: 'var(--surface-2)',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '10px'
                          }}>
                            {keyword}
                          </span>
                        ))}
                        {category.keywords.length > 8 && (
                          <span style={{ fontSize: '10px', color: 'var(--text-2)' }}>
                            +{category.keywords.length - 8} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Discovery Results Summary */}
      {discoveryResults && (
        <div style={{ 
          padding: '15px', 
          backgroundColor: 'var(--success-soft)', 
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--success)'
        }}>
          <h4>Discovery Summary</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
            <div>
              <strong>Method:</strong> {discoveryResults.method}
            </div>
            <div>
              <strong>Categories:</strong> {discoveredCategories.length}
            </div>
            <div>
              <strong>Records Analyzed:</strong> {sampleRecords?.length || 0}
            </div>
            <div>
              <strong>Status:</strong> {discoveryResults.status}
            </div>
          </div>
          
          {discoveryResults.ai_analysis && (
            <div style={{ marginTop: '15px', padding: '10px', backgroundColor: 'var(--surface-2)', borderRadius: 'var(--radius-sm)' }}>
              <strong>AI Analysis:</strong>
              <div style={{ fontSize: '12px', marginTop: '5px', fontFamily: 'monospace' }}>
                {JSON.stringify(discoveryResults.ai_analysis, null, 2)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Re-run after completion or failure */}
      {(discoveryStatus === 'completed' || discoveryStatus === 'failed') && (
        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <button
            className="btn btn-secondary"
            onClick={startDiscovery}
            style={{ padding: '10px 20px' }}
          >
            Re-run Discovery
          </button>
        </div>
      )}

      {/* Action Button */}
      {discoveryStatus === 'idle' && (
        <div style={{ textAlign: 'center' }}>
          <button
            className="btn btn-primary"
            onClick={startDiscovery}
            disabled={!sampleRecords || sampleRecords.length === 0}
            style={{ padding: '14px 32px', fontSize: '16px' }}
          >
            🔍 Start Category Discovery
          </button>
        </div>
      )}
    </div>
  )
}

export default CategoryDiscovery
