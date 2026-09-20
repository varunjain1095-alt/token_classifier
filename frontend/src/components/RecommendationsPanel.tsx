import React, { useState, useEffect } from 'react'

interface Recommendation {
  type: string
  priority: 'high' | 'medium' | 'low'
  confidence: number
  title: string
  description: string
  action: string
  current_value: any
  suggested_value: any
  impact: string
  applied?: boolean
}

interface RecommendationSummary {
  total_recommendations: number
  priority_distribution: {
    high: number
    medium: number
    low: number
  }
  type_distribution: { [key: string]: number }
  overall_health_score: number
  top_priority_action: string
  estimated_impact: string
}

interface RecommendationsPanelProps {
  analysisResults: any
  discoveryResults: any
  currentConfig: any
  costEstimate: any
  previewResults: any
  onRecommendationsComplete: (recommendations: any) => void
}

const RecommendationsPanel: React.FC<RecommendationsPanelProps> = ({
  analysisResults,
  discoveryResults,
  currentConfig,
  costEstimate,
  previewResults,
  onRecommendationsComplete
}) => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [summary, setSummary] = useState<RecommendationSummary | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [appliedRecommendations, setAppliedRecommendations] = useState<Set<number>>(new Set())
  const [recommendationId, setRecommendationId] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>('all')
  const [filterPriority, setFilterPriority] = useState<string>('all')

  useEffect(() => {
    generateRecommendations()
  }, [analysisResults, discoveryResults, currentConfig, costEstimate])

  const generateRecommendations = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/recommendations/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          analysis_results: analysisResults,
          discovery_results: discoveryResults,
          current_config: currentConfig,
          cost_estimate: costEstimate,
          preview_results: previewResults?.results || {}
        }),
      })

      const data = await response.json()
      if (data.success) {
        setRecommendations(data.recommendation.recommendations || [])
        setSummary(data.recommendation.summary)
        setRecommendationId(data.recommendation_id)
        onRecommendationsComplete(data.recommendation)
      } else {
        setError(data.error || 'Failed to generate recommendations')
      }
    } catch (error) {
      setError('Recommendation generation failed: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const applyRecommendation = async (index: number) => {
    try {
      const response = await fetch(`/api/recommendations/apply/${index}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          recommendation_id: recommendationId,
          recommendation_index: index,
          user_id: 'current_user'
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        setAppliedRecommendations(prev => new Set([...prev, index]))
        // Update the recommendation in the list
        const updatedRecs = [...recommendations]
        updatedRecs[index] = { ...updatedRecs[index], applied: true }
        setRecommendations(updatedRecs)
      }
    } catch (error) {
      console.error('Failed to apply recommendation:', error)
    }
  }

  const getPriorityColor = (priority: string) => {
    const colors = {
      'high': 'var(--danger)',
      'medium': 'var(--warning)',
      'low': 'var(--success)'
    }
    return colors[priority as keyof typeof colors] || 'var(--text-2)'
  }

  const getTypeIcon = (type: string) => {
    const icons = {
      'configuration': '⚙️',
      'categories': '🏷️',
      'sampling': '🎯',
      'cost_optimization': '💰',
      'accuracy_improvement': '📈'
    }
    return icons[type as keyof typeof icons] || '📋'
  }

  const getHealthScoreColor = (score: number) => {
    if (score >= 80) return 'var(--success)'
    if (score >= 60) return 'var(--warning)'
    return 'var(--danger)'
  }

  const filteredRecommendations = recommendations.filter(rec => {
    const typeMatch = filterType === 'all' || rec.type === filterType
    const priorityMatch = filterPriority === 'all' || rec.priority === filterPriority
    return typeMatch && priorityMatch
  })

  const getUniqueTypes = () => {
    const types = [...new Set(recommendations.map(r => r.type))]
    return types
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <div style={{ fontSize: '18px', marginBottom: '10px' }}>💡</div>
        <div>Generating intelligent recommendations...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ 
        padding: '20px', 
        backgroundColor: 'var(--danger-soft)', 
        border: '1px solid var(--danger)',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--danger)'
      }}>
        <strong>Error:</strong> {error}
      </div>
    )
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Recommendations</h3>
      <p>AI-powered suggestions to optimize your classification configuration.</p>
      
      {/* Summary */}
      {summary && (
        <div style={{ 
          padding: '20px', 
          backgroundColor: 'var(--surface-2)', 
          borderRadius: 'var(--radius-sm)',
          marginBottom: '30px',
          border: '1px solid var(--border)'
        }}>
          <h4>Summary</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getHealthScoreColor(summary.overall_health_score) }}>
                {summary.overall_health_score.toFixed(0)}
              </div>
              <div>Health Score</div>
            </div>
            
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--danger)' }}>
                {summary.priority_distribution.high}
              </div>
              <div>High Priority</div>
            </div>
            
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--warning)' }}>
                {summary.priority_distribution.medium}
              </div>
              <div>Medium Priority</div>
            </div>
            
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--success)' }}>
                {summary.priority_distribution.low}
              </div>
              <div>Low Priority</div>
            </div>
          </div>
          
          <div style={{ marginTop: '15px', padding: '10px', backgroundColor: 'var(--info-soft)', borderRadius: 'var(--radius-sm)' }}>
            <strong>Top Priority:</strong> {summary.top_priority_action}<br />
            <strong>Impact:</strong> {summary.estimated_impact}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
        <div>
          <label style={{ marginRight: '8px', fontWeight: 'bold' }}>Type:</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{ padding: '5px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
          >
            <option value="all">All Types</option>
            {getUniqueTypes().map(type => (
              <option key={type} value={type}>{type.replace('_', ' ')}</option>
            ))}
          </select>
        </div>
        
        <div>
          <label style={{ marginRight: '8px', fontWeight: 'bold' }}>Priority:</label>
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            style={{ padding: '5px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
          >
            <option value="all">All Priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
        
        <div style={{ marginLeft: 'auto', fontSize: '14px', color: 'var(--text-2)' }}>
          {filteredRecommendations.length} of {recommendations.length} recommendations
        </div>
      </div>

      {/* Recommendations List */}
      <div style={{ display: 'grid', gap: '15px' }}>
        {filteredRecommendations.map((rec, index) => {
          const actualIndex = recommendations.indexOf(rec)
          const isApplied = appliedRecommendations.has(actualIndex) || rec.applied
          
          return (
            <div key={index} style={{
              padding: '20px',
              backgroundColor: isApplied ? 'var(--success-soft)' : 'var(--surface)',
              border: `2px solid ${getPriorityColor(rec.priority)}`,
              borderRadius: 'var(--radius)',
              opacity: isApplied ? 0.7 : 1
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '15px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '20px' }}>{getTypeIcon(rec.type)}</span>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '16px' }}>{rec.title}</h4>
                    <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                      {rec.type.replace('_', ' ')} • {(rec.confidence * 100).toFixed(0)}% confidence
                    </div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <span style={{ 
                    padding: '4px 12px', 
                    backgroundColor: getPriorityColor(rec.priority),
                    color: 'white',
                    borderRadius: '12px',
                    fontSize: '11px',
                    fontWeight: 'bold'
                  }}>
                    {rec.priority.toUpperCase()}
                  </span>
                  
                  {isApplied && (
                    <span style={{ 
                      padding: '4px 12px', 
                      backgroundColor: 'var(--success)',
                      color: 'white',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontWeight: 'bold'
                    }}>
                      APPLIED
                    </span>
                  )}
                </div>
              </div>
              
              <div style={{ marginBottom: '15px' }}>
                <p style={{ margin: '0 0 10px 0', fontSize: '14px' }}>{rec.description}</p>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', fontSize: '13px' }}>
                  <div>
                    <strong>Current:</strong> {String(rec.current_value)}
                  </div>
                  <div>
                    <strong>Suggested:</strong> {String(rec.suggested_value)}
                  </div>
                </div>
                
                <div style={{ marginTop: '10px', fontSize: '13px', color: 'var(--text-2)' }}>
                  <strong>Action:</strong> {rec.action}
                </div>
                
                <div style={{ marginTop: '5px', fontSize: '13px', color: 'var(--success)' }}>
                  <strong>Impact:</strong> {rec.impact}
                </div>
              </div>
              
              {!isApplied && (
                <div style={{ textAlign: 'right' }}>
                  <button
                    className="btn btn-primary"
                    onClick={() => applyRecommendation(actualIndex)}
                    style={{ padding: '8px 16px' }}
                  >
                    Apply Recommendation
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {filteredRecommendations.length === 0 && recommendations.length > 0 && (
        <div style={{ 
          textAlign: 'center', 
          padding: '40px', 
          color: 'var(--text-2)',
          backgroundColor: 'var(--surface-2)',
          borderRadius: 'var(--radius-sm)'
        }}>
          No recommendations match the selected filters.
        </div>
      )}

      {recommendations.length === 0 && !loading && (
        <div style={{ 
          textAlign: 'center', 
          padding: '40px', 
          color: 'var(--text-2)',
          backgroundColor: 'var(--success-soft)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--success)'
        }}>
          <div style={{ fontSize: '18px', marginBottom: '10px' }}>✅</div>
          <div>No recommendations needed - your configuration looks good!</div>
        </div>
      )}
    </div>
  )
}

export default RecommendationsPanel
