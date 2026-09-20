import React, { useState, useEffect } from 'react'

interface AnalysisResult {
  accuracy?: {
    evaluated?: boolean
    overall_accuracy: number | null
    matches: number
    mismatches: number
    no_expectation: number
    comparable_results: number
    confidence_breakdown: any
  }
  confidence_distribution?: {
    numeric_scores: any
    level_counts: any
    score_ranges: any
  }
  error_patterns?: {
    total_errors: number
    error_types: any
    provider_errors: any
    error_records: any[]
    error_rate: number
  }
  category_distribution?: {
    total_classified: number
    categories: any
    category_stats: any
    most_common: any[]
  }
  performance_metrics?: {
    successful_requests: number
    token_statistics: any
    average_tokens_per_request: number
  }
  insights?: string[]
  recommendations?: any[]
}

interface ResultsAnalyzerProps {
  previewResults: any
  expectations: any[]
  sampleRecords: any[]
  onAnalysisComplete: (analysis: any) => void
}

const ResultsAnalyzer: React.FC<ResultsAnalyzerProps> = ({
  previewResults,
  expectations,
  sampleRecords,
  onAnalysisComplete
}) => {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [recalibration, setRecalibration] = useState<any>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null)

  useEffect(() => {
    if (previewResults && previewResults.results) {
      performAnalysis()
    }
  }, [previewResults, expectations])

  const performAnalysis = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/results/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          results: previewResults.results?.results || [],
          expectations: expectations || []
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        setAnalysis(data.analysis)
        
        // Perform recalibration
        const recalibrationResponse = await fetch('/api/results/recalibrate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            preview_results: previewResults.results?.results || [],
            token_estimates: previewResults.token_estimate || {},
            actual_usage: previewResults.results?.results?.map((r: any) => r.usage) || [],
            expectations: expectations || []
          }),
        })
        
        const recalibrationData = await recalibrationResponse.json()
        if (recalibrationData.success) {
          setRecalibration(recalibrationData.recalibration)
        }
        
        onAnalysisComplete({
          analysis: data.analysis,
          recalibration: recalibrationData.recalibration
        })
      } else {
        setError(data.error || 'Analysis failed')
      }
    } catch (error) {
      setError('Analysis failed: ' + error)
    } finally {
      setLoading(false)
    }
  }

  const getAccuracyColor = (accuracy: number) => {
    if (accuracy >= 80) return 'var(--success)'
    if (accuracy >= 60) return 'var(--warning)'
    return 'var(--danger)'
  }

  const getConfidenceColor = (level: string) => {
    const colors = {
      'high': 'var(--success)',
      'medium': 'var(--warning)',
      'low': 'var(--danger)'
    }
    return colors[level as keyof typeof colors] || 'var(--text-2)'
  }

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`
  }

  // Map each category label to the records (id + review text) under it,
  // for the hover popover in Category Distribution.
  const textsById: Record<string, string> = {}
  for (const r of sampleRecords || []) {
    if (r?.id != null) textsById[r.id] = r.review_text || ''
  }
  const recordsByCategory: Record<string, { id: string, text: string }[]> = {}
  for (const r of previewResults?.results?.results || []) {
    if (!r?.success) continue
    const cat = r?.result?.classification?.primary_category || 'Unaccounted'
    ;(recordsByCategory[cat] ||= []).push({
      id: r.record_id || '?',
      text: textsById[r.record_id] || ''
    })
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <div style={{ fontSize: '18px', marginBottom: '10px' }}>📊</div>
        <div>Analyzing results and recalibrating...</div>
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
      <h3>Results Analysis & Recalibration</h3>
      
      {/* Accuracy Analysis */}
      {analysis?.accuracy && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Accuracy Analysis</h4>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
            gap: '15px',
            marginBottom: '20px'
          }}>
            <div style={{ padding: '15px', backgroundColor: 'var(--success-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysis.accuracy.overall_accuracy == null ? 'var(--text-2)' : getAccuracyColor(analysis.accuracy.overall_accuracy) }}>
                {analysis.accuracy.overall_accuracy == null ? 'Not evaluated' : formatPercentage(analysis.accuracy.overall_accuracy)}
              </div>
              <div>Overall Accuracy</div>
            </div>

            <div style={{ padding: '15px', backgroundColor: 'var(--info-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysis.accuracy.overall_accuracy == null ? 'var(--text-2)' : 'var(--success)' }}>
                {analysis.accuracy.overall_accuracy == null ? 'Not evaluated' : analysis.accuracy.matches}
              </div>
              <div>Matches</div>
            </div>

            <div style={{ padding: '15px', backgroundColor: 'var(--danger-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysis.accuracy.overall_accuracy == null ? 'var(--text-2)' : 'var(--danger)' }}>
                {analysis.accuracy.overall_accuracy == null ? 'Not evaluated' : analysis.accuracy.mismatches}
              </div>
              <div>Mismatches</div>
            </div>
            
            <div style={{ padding: '15px', backgroundColor: 'var(--warning-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--warning)' }}>
                {analysis.accuracy.comparable_results}
              </div>
              <div>Comparable</div>
            </div>
          </div>
          
          {/* Confidence Breakdown */}
          {analysis.accuracy.confidence_breakdown && (
            <div style={{ marginBottom: '20px' }}>
              <h5>Accuracy by Confidence Level</h5>
              <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
                {Object.entries(analysis.accuracy.confidence_breakdown).map(([confidence, data]: [string, any]) => (
                  <div key={confidence} style={{ 
                    padding: '10px', 
                    backgroundColor: getConfidenceColor(confidence) + '20', 
                    borderRadius: 'var(--radius-sm)',
                    border: `1px solid ${getConfidenceColor(confidence)}`
                  }}>
                    <strong style={{ color: getConfidenceColor(confidence) }}>
                      {confidence.toUpperCase()}:
                    </strong> {formatPercentage(data.accuracy)} ({data.count} samples)
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Category Distribution */}
      {analysis?.category_distribution && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Category Distribution</h4>
          <div style={{ 
            padding: '15px', 
            backgroundColor: 'var(--surface-2)', 
            borderRadius: 'var(--radius-sm)' 
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
              {analysis.category_distribution.most_common.map(([category, count]: [string, number]) => (
                <div
                  key={category}
                  style={{ textAlign: 'center', position: 'relative', cursor: 'default' }}
                  onMouseEnter={() => setHoveredCategory(category)}
                  onMouseLeave={() => setHoveredCategory(null)}
                >
                  <div style={{ fontSize: '18px', fontWeight: 'bold' }}>{count}</div>
                  <div style={{ fontSize: '12px', color: category === 'Unaccounted' ? 'var(--danger)' : 'var(--text-2)' }}>{category}</div>
                  {hoveredCategory === category && recordsByCategory[category]?.length > 0 && (
                    <div style={{
                      position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
                      zIndex: 10, minWidth: '280px', maxWidth: '360px', maxHeight: '240px', overflowY: 'auto',
                      backgroundColor: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '6px',
                      padding: '10px', boxShadow: '0 4px 12px rgba(0,0,0,0.15)', textAlign: 'left'
                    }}>
                      {recordsByCategory[category].map(rec => (
                        <div key={rec.id} style={{ marginBottom: '8px', fontSize: '12px' }}>
                          <strong>{rec.id}</strong>
                          <div style={{ color: 'var(--text-2)' }}>
                            {rec.text ? (rec.text.length > 140 ? rec.text.slice(0, 140) + '…' : rec.text) : '(text unavailable)'}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '10px' }}>
              Total classified: {analysis.category_distribution.total_classified} of {analysis.successful_results ?? analysis.category_distribution.total_classified} successful results
            </div>
          </div>
        </div>
      )}

      {/* Error Patterns */}
      {analysis?.error_patterns && analysis.error_patterns.total_errors > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Error Analysis</h4>
          <div style={{ 
            padding: '15px', 
            backgroundColor: 'var(--danger-soft)', 
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--danger)'
          }}>
            <div style={{ marginBottom: '15px' }}>
              <strong>Error Rate:</strong> {formatPercentage(analysis.error_patterns.error_rate)} 
              ({analysis.error_patterns.total_errors} errors)
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              {Object.entries(analysis.error_patterns.error_types).map(([error, count]: [string, number]) => (
                <div key={error} style={{ fontSize: '12px' }}>
                  <strong>{error}:</strong> {count} occurrences
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Performance Metrics */}
      {analysis?.performance_metrics && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Performance Metrics</h4>
          <div style={{ 
            padding: '15px', 
            backgroundColor: 'var(--surface-2)', 
            borderRadius: 'var(--radius-sm)' 
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
              <div>
                <strong>Successful Requests:</strong><br />
                {analysis.performance_metrics.successful_requests}
              </div>
              <div>
                <strong>Avg Tokens/Request:</strong><br />
                {analysis.performance_metrics.average_tokens_per_request?.toFixed(0) || 0}
              </div>
              {analysis.performance_metrics.token_statistics && (
                <>
                  <div>
                    <strong>Total Tokens Used:</strong><br />
                    {analysis.performance_metrics.token_statistics.total_tokens_used || 0}
                  </div>
                  <div>
                    <strong>Token Efficiency:</strong><br />
                    {(analysis.performance_metrics.token_statistics.token_efficiency * 100).toFixed(1)}%
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Reliability Audit — verdicts + flags from the preview run */}
      {(() => {
        const batch = previewResults?.results || {}
        const consistency: any[] = batch.consistency || []
        const diag = batch.diagnostics || {}
        const stab = batch.stability
        if (!consistency.length && !diag.flag_counts && !stab) return null
        const verdictCounts = consistency.reduce((acc: any, c: any) => {
          acc[c.verdict] = (acc[c.verdict] || 0) + 1
          return acc
        }, {})
        const flagged = Object.entries(diag.records || {})
          .filter(([, d]: [string, any]) => d.flags?.length)
        return (
          <div style={{ marginBottom: '30px' }}>
            <h4>Reliability Audit</h4>
            <div style={{ padding: '15px', backgroundColor: 'var(--warning-soft)', border: '1px solid var(--warning)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-2)', marginBottom: '10px', lineHeight: '1.5' }}>
                Two different checks run on every result, so their counts can differ:
                <br />• <strong>Audit verdicts</strong> (supported / questionable / unsupported) — a second model pass judging whether the <em>category fits the review</em>.
                <br />• <strong>Flagged records</strong> — automatic rule checks, e.g. whether the quoted evidence appears <em>verbatim</em> in the review text.
                <br />A record can be flagged (its evidence quote was paraphrased) while its category is still judged supported — flags catch mechanical issues, verdicts judge whether the label itself makes sense.
              </div>
              <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', marginBottom: '10px' }}>
                {(['supported', 'questionable', 'unsupported'] as const).map(v => (
                  <span key={v} className={`chip chip-${v === 'supported' ? 'success' : v === 'questionable' ? 'warning' : 'danger'}`} style={{ fontSize: '13px' }}>
                    {v}: {verdictCounts[v] || 0}
                  </span>
                ))}
                {stab && (
                  <span className="chip chip-info" style={{ fontSize: '13px' }}>
                    label stability: {stab.stability_rate}% ({stab.changed} changed)
                  </span>
                )}
              </div>
              {flagged.length > 0 && (
                <div style={{ fontSize: '12px' }}>
                  <strong>Flagged records:</strong>
                  {flagged.map(([rid, d]: [string, any]) => {
                    const verdict = consistency.find(c => c.record_id === rid)?.verdict
                    return (
                      <div key={rid} style={{ padding: '3px 0', color: 'var(--warning)' }}>
                        <strong>{rid}</strong> — flagged: {d.flags.map((f: string) => f.replace(/_/g, ' ')).join(', ')}
                        {verdict && <span className={`chip chip-${verdict === 'supported' ? 'success' : verdict === 'questionable' ? 'warning' : 'danger'}`} style={{ marginLeft: '6px' }}>{verdict}</span>}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )
      })()}

      {/* Insights */}
      {analysis?.insights && analysis.insights.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Insights</h4>
          <div style={{ 
            padding: '15px', 
            backgroundColor: 'var(--info-soft)', 
            borderRadius: 'var(--radius-sm)' 
          }}>
            {analysis.insights.map((insight, index) => (
              <div key={index} style={{ marginBottom: '8px', fontSize: '14px' }}>
                • {insight}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {analysis?.recommendations && analysis.recommendations.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Recommendations</h4>
          <div style={{ display: 'grid', gap: '10px' }}>
            {analysis.recommendations.map((rec, index) => (
              <div key={index} style={{ 
                padding: '15px', 
                backgroundColor: rec.priority === 'high' ? 'var(--danger-soft)' : rec.priority === 'medium' ? 'var(--warning-soft)' : 'var(--success-soft)',
                borderRadius: 'var(--radius-sm)',
                border: `1px solid ${rec.priority === 'high' ? 'var(--danger)' : rec.priority === 'medium' ? 'var(--warning)' : 'var(--success)'}`
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <strong>{rec.type.replace('_', ' ').toUpperCase()}</strong>
                  <span style={{ 
                    padding: '2px 8px', 
                    backgroundColor: rec.priority === 'high' ? 'var(--danger)' : rec.priority === 'medium' ? 'var(--warning)' : 'var(--success)',
                    color: 'white',
                    borderRadius: '12px',
                    fontSize: '10px'
                  }}>
                    {rec.priority.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: '14px', marginBottom: '5px' }}>{rec.description}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-2)' }}><strong>Action:</strong> {rec.action}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recalibration Status */}
      {recalibration && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Recalibration Status</h4>
          <div style={{
            padding: '15px',
            backgroundColor: recalibration.applied ? 'var(--success-soft)' : 'var(--surface-2)',
            borderRadius: 'var(--radius-sm)',
            border: `1px solid ${recalibration.applied ? 'var(--success)' : 'var(--border)'}`
          }}>
            {/* Token-estimate recalibration — separate from classification */}
            <div style={{ marginBottom: '12px' }}>
              <strong>Token-Estimate Recalibration:</strong>
              <span style={{ marginLeft: '10px', fontWeight: 'bold', color:
                recalibration.token_status === 'applied' ? 'var(--success)'
                : recalibration.token_status === 'insufficient_data' ? 'var(--warning)' : 'var(--text-2)' }}>
                {recalibration.token_status === 'applied' ? 'Applied'
                 : recalibration.token_status === 'insufficient_data' ? 'Insufficient data'
                 : 'No adjustment needed'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginBottom: '15px' }}>
              <div>
                <strong>Token Accuracy:</strong><br />
                {recalibration.token_analysis?.accuracy_percentage == null
                  ? 'Insufficient data'
                  : formatPercentage(recalibration.token_analysis.accuracy_percentage)}
              </div>
              <div>
                <strong>Estimated vs Actual:</strong><br />
                {recalibration.token_analysis?.estimated_total != null && recalibration.token_analysis?.actual_total != null
                  ? `${recalibration.token_analysis.estimated_total} est / ${recalibration.token_analysis.actual_total} actual`
                  : 'N/A'}
              </div>
              <div>
                <strong>Token Multiplier:</strong><br />
                {recalibration.calibration_factors?.token_multiplier != null
                  ? `×${recalibration.calibration_factors.token_multiplier.toFixed(2)}${recalibration.token_status === 'applied' ? ' (applied this run)' : ''}`
                  : 'N/A'}
              </div>
            </div>

            {/* Classification recalibration — requires expectations */}
            <div style={{ marginBottom: '12px', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
              <strong>Classification Recalibration:</strong>
              <span style={{ marginLeft: '10px', fontWeight: 'bold', color:
                recalibration.classification_status === 'applied' ? 'var(--success)'
                : recalibration.classification_status === 'not_evaluated' ? 'var(--warning)' : 'var(--text-2)' }}>
                {recalibration.classification_status === 'applied' ? 'Applied'
                 : recalibration.classification_status === 'not_evaluated' ? 'Not evaluated'
                 : 'No adjustment needed'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
              <div>
                <strong>Classification Accuracy:</strong><br />
                {recalibration.accuracy_analysis?.overall_accuracy == null
                  ? 'Not evaluated'
                  : formatPercentage(recalibration.accuracy_analysis.overall_accuracy)}
              </div>
              <div>
                <strong>Optimal Threshold:</strong><br />
                {recalibration.confidence_analysis?.optimal_threshold == null
                  ? 'N/A'
                  : recalibration.confidence_analysis.optimal_threshold.toFixed(2)}
              </div>
              <div>
                <strong>Recommendations:</strong><br />
                {recalibration.recommendations?.length || 0}
              </div>
            </div>
            {recalibration.classification_status === 'not_evaluated' && (
              <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-2)' }}>
                Add expectations to evaluate classification quality and tune the confidence threshold.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ResultsAnalyzer
