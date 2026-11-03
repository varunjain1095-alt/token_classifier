import React, { useState, useEffect } from 'react'

interface PreviewResult {
  record_id: string
  result: {
    success: boolean
    classification: any
    raw_content: string
    format: string
  }
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
  model: string
}

interface PreviewAnalysis {
  total_results: number
  total_expectations: number
  comparable_results: number
  matches: number
  mismatches: number
  no_expectation: number
  evaluated?: boolean
  accuracy_percentage: number | null
  detailed_results: any[]
}

interface PreviewExecutorProps {
  sampleRecords: any[]
  experimentConfig: any
  expectations: any[]
  onPreviewComplete: (results: any) => void
}

const PreviewExecutor: React.FC<PreviewExecutorProps> = ({ 
  sampleRecords, 
  experimentConfig, 
  expectations, 
  onPreviewComplete 
}) => {
  const [previewStatus, setPreviewStatus] = useState<string>('idle')
  const [previewResults, setPreviewResults] = useState<any>(null)
  const [analysis, setAnalysis] = useState<PreviewAnalysis | null>(null)
  const [quotaInfo, setQuotaInfo] = useState<any>(null)
  const [apiKey, setApiKey] = useState<string>('')
  const [useCustomApiKey, setUseCustomApiKey] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [previewModel, setPreviewModel] = useState<string>('')
  const [taxonomy, setTaxonomy] = useState<any>(null)
  const [diagnostics, setDiagnostics] = useState<any>(null)
  const [runFingerprint, setRunFingerprint] = useState<string>('')
  const [stability, setStability] = useState<any>(null)
  const [consistency, setConsistency] = useState<any[]>([])
  const [diagnosticUsage, setDiagnosticUsage] = useState<any>(null)
  const [unassignedThemes, setUnassignedThemes] = useState<string[]>([])

  useEffect(() => {
    checkQuota()
    loadPreviewModel()
  }, [])

  // Show the actual configured preview model (OPENAI_MODEL_NAME). If the
  // session expired, create a fresh anonymous session and retry once so the
  // Execute button never stays disabled after a refresh.
  const loadPreviewModel = async (retried = false) => {
    try {
      let r = await fetch('/api/tokens/pricing-info', { credentials: 'include' })
      if (!r.ok && !retried) {
        await fetch('/api/session/anonymous', { method: 'POST', credentials: 'include' })
        r = await fetch('/api/tokens/pricing-info', { credentials: 'include' })
      }
      const d = r.ok ? await r.json() : null
      const model = d?.pricing_info?.preview_model || d?.preview_model
      if (model) setPreviewModel(model)
    } catch {}
  }

  const checkQuota = async () => {
    try {
      const response = await fetch('/api/preview/quota')
      const data = await response.json()
      if (data.success) {
        setQuotaInfo(data.quota_info)
      }
    } catch (error) {
      console.error('Failed to check quota:', error)
    }
  }

  const executePreview = async (regenerateTaxonomy = false, stabilityRun = false) => {
    if (stabilityRun) {
      const estTokens = (sampleRecords?.length || 0) * 800
      const ok = window.confirm(
        `Stability check reruns the identical classification batch to measure label consistency (labels are compared, not changed).\n\n` +
        `Estimated total cost: ~${estTokens} tokens on ${previewModel || 'the configured model'} (2 batches).\n\n` +
        `Proceed?`)
      if (!ok) return
    }
    setLoading(true)
    setError(null)
    setPreviewStatus('running')

    try {
      const requestData = {
        sample_records: sampleRecords,
        experiment_config: experimentConfig,
        expectations: expectations,
        api_key: useCustomApiKey ? apiKey : null,
        regenerate_taxonomy: regenerateTaxonomy,
        stability_run: stabilityRun
      }
      
      const response = await fetch('/api/preview/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      })
      
      const data = await response.json()
      
      if (data.success) {
        setPreviewResults(data.results)
        setPreviewStatus(data.status || 'completed')
        setTaxonomy(data.taxonomy || null)
        setDiagnostics(data.diagnostics || null)
        setRunFingerprint(data.run_fingerprint || '')
        setStability(data.stability || null)
        setConsistency(data.consistency || [])
        setDiagnosticUsage(data.diagnostic_usage || null)
        setUnassignedThemes(data.unassigned_guidance_themes || [])

        // Get analysis
        const analysisResponse = await fetch(`/api/preview/analysis/${data.preview_id}`)
        const analysisData = await analysisResponse.json()
        if (analysisData.success) {
          setAnalysis(analysisData.analysis)
          if (analysisData.analysis?.taxonomy) setTaxonomy(analysisData.analysis.taxonomy)
          if (analysisData.analysis?.diagnostics) setDiagnostics(analysisData.analysis.diagnostics)
        }
        
        onPreviewComplete({
          preview_id: data.preview_id,
          results: data.results,
          analysis: analysisData.analysis
        })
      } else {
        setError(data.error || data.detail || 'Preview execution failed')
        setPreviewStatus('failed')
      }
    } catch (error) {
      setError('Preview execution failed: ' + error)
      setPreviewStatus('failed')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    const colors = {
      'idle': 'var(--text-2)',
      'running': 'var(--warning)',
      'completed': 'var(--success)',
      'failed': 'var(--danger)'
    }
    return colors[status as keyof typeof colors] || 'var(--text-2)'
  }

  const getAccuracyColor = (accuracy: number) => {
    if (accuracy >= 80) return 'var(--success)'
    if (accuracy >= 60) return 'var(--warning)'
    return 'var(--danger)'
  }

  // Display stored snake_case labels readably; raw values are preserved
  // in the data and shown via the title attribute / raw JSON.
  const formatLabel = (label: any) =>
    typeof label === 'string' ? label.replace(/_/g, ' ') : String(label)

  const isDiscoveryMode = () => {
    const c = experimentConfig?.config || {}
    return c.classification_type === 'undefined' || c.category_mode === 'discovery'
  }

  const formatClassification = (classification: any) => {
    if (typeof classification === 'object') {
      return JSON.stringify(classification, null, 2)
    }
    return String(classification)
  }

  const canExecutePreview = () => {
    if (!previewModel) return false
    if (!sampleRecords || sampleRecords.length === 0) return false
    if (!experimentConfig) return false
    if (quotaInfo?.exceeded?.any) return false
    if (useCustomApiKey && !apiKey.trim()) return false
    return true
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Classification Preview</h3>
      <p>Execute AI classification on your selected sample to see how it performs.</p>
      
      {/* Quota Information */}
      {quotaInfo && (
        <div style={{ 
          padding: '15px', 
          backgroundColor: quotaInfo.exceeded?.any ? 'var(--danger-soft)' : 'var(--info-soft)', 
          borderRadius: 'var(--radius-sm)', 
          marginBottom: '20px',
          border: quotaInfo.exceeded?.any ? '1px solid var(--danger)' : '1px solid var(--info)'
        }}>
          <strong>Quota Status:</strong> 
          {quotaInfo.exceeded?.any ? (
            <span style={{ color: 'var(--danger)', marginLeft: '10px' }}>
              Quota exceeded - {quotaInfo.usage.hourly}/{quotaInfo.limits.requests_per_hour} hourly, 
              {quotaInfo.usage.daily}/{quotaInfo.limits.requests_per_day} daily
            </span>
          ) : (
            <span style={{ color: 'var(--success)', marginLeft: '10px' }}>
              Available - {quotaInfo.remaining.hourly} hourly, {quotaInfo.remaining.daily} daily remaining
            </span>
          )}
        </div>
      )}

      {/* API Key Configuration */}
      <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: 'var(--surface-2)', borderRadius: 'var(--radius-sm)' }}>
        <label style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
          <input
            type="checkbox"
            checked={useCustomApiKey}
            onChange={(e) => setUseCustomApiKey(e.target.checked)}
            style={{ marginRight: '8px' }}
          />
          <strong>Use Custom API Key</strong>
        </label>
        
        {useCustomApiKey && (
          <div>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your OpenAI API key..."
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                marginTop: '5px'
              }}
            />
            <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '5px' }}>
              API key is stored in session memory only and never persisted
            </div>
          </div>
        )}
      </div>

      {/* Preview Configuration */}
      <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: 'var(--surface-2)', borderRadius: 'var(--radius-sm)' }}>
        <h4>Preview Configuration</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
          <div>
            <strong>Sample Size:</strong> {sampleRecords?.length || 0} records
          </div>
          <div>
            <strong>Model:</strong> {experimentConfig?.config?.model || previewModel || 'loading...'}
          </div>
          <div>
            <strong>Max Tokens:</strong> {experimentConfig?.config?.max_tokens || 150}
          </div>
          <div>
            <strong>Temperature:</strong> {experimentConfig?.config?.temperature || 0.1}
          </div>
          <div>
            <strong>Consistency check:</strong>{' '}
            ~{(sampleRecords?.length || 0) * 170} tokens
            (≈${(((sampleRecords?.length || 0) * 150 * 0.05 + (sampleRecords?.length || 0) * 40 * 0.4) / 1e6).toFixed(6)})
          </div>
        </div>
      </div>

      {/* Draft taxonomy (discovery mode) */}
      {taxonomy && isDiscoveryMode() && (
        <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: 'var(--primary-soft)', borderRadius: 'var(--radius-sm)', fontSize: '13px' }}>
          <strong>Draft Taxonomy</strong>
          <span style={{ marginLeft: '10px', color: 'var(--text-2)' }}>
            v{taxonomy.version} · id {String(taxonomy.id).slice(0, 8)} · {taxonomy.labels?.length || 0} themes
          </span>
          <div style={{ marginTop: '8px' }}>
            {(taxonomy.labels || []).map((l: string) => (
              <span key={l} title={l} style={{
                display: 'inline-block', padding: '2px 8px', margin: '2px 4px 2px 0',
                backgroundColor: 'var(--surface)', border: '1px solid var(--primary)', borderRadius: 'var(--radius-sm)'
              }}>
                {formatLabel(l)}
              </span>
            ))}
          </div>
          {taxonomy.sample_mismatch && (
            <div style={{ marginTop: '8px', color: 'var(--warning)', fontSize: '12px' }}>
              Warning: {taxonomy.sample_mismatch.message} ({Math.round((taxonomy.sample_mismatch.overlap_ratio || 0) * 100)}% sample overlap). Consider Regenerate Taxonomy.
            </div>
          )}
          {unassignedThemes.length > 0 && (
            <div style={{ marginTop: '6px', color: 'var(--warning)', fontSize: '12px' }}>
              Warning: suggested themes never assigned to any record: {unassignedThemes.join(', ')}. Your theme guidance may not match this data.
            </div>
          )}
        </div>
      )}

      {/* Execute Button */}
      <div style={{ textAlign: 'center', marginBottom: '30px' }}>
        <button
          className="btn btn-primary"
          onClick={() => executePreview(false)}
          disabled={!canExecutePreview() || loading}
          style={{ padding: '14px 32px', fontSize: '16px' }}
        >
          {loading ? 'Executing Preview...' : 'Execute Classification Preview'}
        </button>
        {isDiscoveryMode() && taxonomy && (
          <button
            className="btn btn-secondary"
            onClick={() => executePreview(true)}
            disabled={!canExecutePreview() || loading}
            style={{ padding: '14px 20px', marginLeft: '10px' }}
          >
            Regenerate Taxonomy
          </button>
        )}
        {previewStatus === 'completed' && !loading && (
          <button
            className="btn btn-secondary"
            onClick={() => executePreview(false, true)}
            disabled={!canExecutePreview()}
            style={{ padding: '14px 20px', marginLeft: '10px' }}
          >
            Run Stability Check
          </button>
        )}
        {!previewModel && (
          <div style={{ fontSize: '12px', color: 'var(--danger)', marginTop: '8px' }}>
            Preview model (OPENAI_MODEL_NAME) not loaded yet. Execution is disabled until it resolves.
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

      {/* Preview Status */}
      {previewStatus !== 'idle' && (
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
            backgroundColor: getStatusColor(previewStatus),
            color: 'white',
            borderRadius: '20px',
            fontWeight: 'bold'
          }}>
            Status: {previewStatus.toUpperCase()}
          </div>
        </div>
      )}

      {/* Results Analysis */}
      {analysis && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Results Analysis</h4>
          
          {/* Summary Stats */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
            gap: '15px',
            marginBottom: '20px'
          }}>
            <div style={{ padding: '15px', backgroundColor: 'var(--success-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysis.accuracy_percentage == null ? 'var(--text-2)' : 'var(--success)' }}>
                {analysis.accuracy_percentage == null ? 'Not evaluated' : analysis.matches}
              </div>
              <div>Matches</div>
            </div>

            <div style={{ padding: '15px', backgroundColor: 'var(--danger-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysis.accuracy_percentage == null ? 'var(--text-2)' : 'var(--danger)' }}>
                {analysis.accuracy_percentage == null ? 'Not evaluated' : analysis.mismatches}
              </div>
              <div>Mismatches</div>
            </div>

            <div style={{ padding: '15px', backgroundColor: 'var(--warning-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--warning)' }}>
                {analysis.no_expectation}
              </div>
              <div>No Expectation</div>
            </div>

            <div style={{ padding: '15px', backgroundColor: 'var(--info-soft)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysis.accuracy_percentage == null ? 'var(--text-2)' : getAccuracyColor(analysis.accuracy_percentage) }}>
                {analysis.accuracy_percentage == null ? 'Not evaluated' : `${analysis.accuracy_percentage}%`}
              </div>
              <div>Accuracy</div>
            </div>
          </div>

          {/* Detailed Results */}
          <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)', backgroundColor: 'var(--surface)' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Record</th>
                  <th>Expected</th>
                  <th>Actual</th>
                  <th>Match</th>
                  <th>Tokens</th>
                </tr>
              </thead>
              <tbody>
                {analysis.detailed_results.map((result, index) => (
                  <tr key={index}>
                    <td style={{ fontSize: '12px' }}>
                      {result.record_id}
                    </td>
                    <td style={{ fontSize: '12px' }}>
                      {result.expected || 'N/A'}
                    </td>
                    <td style={{ fontSize: '12px', maxWidth: '240px' }}>
                      {result.result?.success ? (() => {
                        const cls = result.result.result?.classification
                        const label = cls?.primary_category
                        return (
                          <>
                            {label && (
                              <div title={label} style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                                {formatLabel(label)}
                              </div>
                            )}
                            <details>
                              <summary style={{ cursor: 'pointer', color: 'var(--text-2)', fontSize: '11px' }}>raw</summary>
                              <pre style={{ fontSize: '11px', margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>
                                {formatClassification(cls)}
                              </pre>
                            </details>
                          </>
                        )
                      })() : 'Failed'}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {result.match === null ? 'N/A' :
                        result.match ? '✓' : '✗'}
                    </td>
                    <td style={{ fontSize: '12px' }}>
                      {result.result?.usage?.total_tokens || 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Reliability Diagnostics (separate from raw results) */}
      {(diagnostics || runFingerprint || stability || consistency.length > 0) && (
        <div style={{ marginBottom: '30px', padding: '15px', backgroundColor: 'var(--warning-soft)', border: '1px solid var(--warning)', borderRadius: 'var(--radius-sm)' }}>
          <h4>Reliability Diagnostics</h4>
          <div style={{ fontSize: '12px', color: 'var(--text-2)', marginBottom: '10px' }}>
            {runFingerprint && <span>Run fingerprint: <code>{runFingerprint}</code></span>}
            {taxonomy && <span style={{ marginLeft: '12px' }}>Taxonomy v{taxonomy.version} ({String(taxonomy.id).slice(0, 8)})</span>}
            {stability && (
              <span style={{ marginLeft: '12px' }}>
                Stability: {stability.stability_rate}% ({stability.changed}/{stability.total} labels changed)
              </span>
            )}
          </div>
          {diagnostics?.flag_counts && Object.keys(diagnostics.flag_counts).length > 0 ? (
            <div style={{ marginBottom: '10px' }}>
              {Object.entries(diagnostics.flag_counts).map(([flag, count]) => (
                <span key={flag} style={{
                  display: 'inline-block', padding: '2px 8px', margin: '2px 6px 2px 0',
                  backgroundColor: 'var(--warning-soft)', border: '1px solid var(--warning)',
                  borderRadius: 'var(--radius-sm)', fontSize: '12px'
                }}>
                  {flag.replace(/_/g, ' ')}: {String(count)}
                </span>
              ))}
            </div>
          ) : diagnostics ? (
            <div style={{ fontSize: '12px', color: 'var(--success)', marginBottom: '10px' }}>No reliability flags.</div>
          ) : null}
          {diagnostics?.records && (
            <div style={{ maxHeight: '200px', overflowY: 'auto', fontSize: '12px' }}>
              {Object.entries(diagnostics.records).map(([rid, d]: [string, any]) => {
                const verdict = consistency.find(c => c.record_id === rid)
                const verdictColor = verdict?.verdict === 'supported' ? 'var(--success)'
                  : verdict?.verdict === 'questionable' ? 'var(--warning)' : 'var(--danger)'
                return (
                  <div key={rid} style={{ padding: '4px 0', borderBottom: '1px solid var(--surface-2)' }}>
                    <strong>{rid}</strong>
                    {d.flags?.length ? (
                      <span style={{ color: 'var(--warning)' }}>: {d.flags.map((f: string) => f.replace(/_/g, ' ')).join(', ')}</span>
                    ) : (
                      <span style={{ color: 'var(--success)' }}>: ok</span>
                    )}
                    {verdict && (
                      <span title={verdict.reason} style={{ color: verdictColor }}>
                        {' '}· {verdict.verdict}: {verdict.reason}
                      </span>
                    )}
                    {stability?.records?.[rid] && !stability.records[rid].stable && (
                      <span style={{ color: 'var(--danger)' }}>
                        {' '}· stability: {formatLabel(stability.records[rid].run_a)} → {formatLabel(stability.records[rid].run_b)}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
          {diagnosticUsage && (
            <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '8px' }}>
              Consistency check ({diagnosticUsage.model}): {diagnosticUsage.total_tokens} tokens
              ({diagnosticUsage.prompt_tokens} in / {diagnosticUsage.completion_tokens} out)
              · actual cost ${Number(diagnosticUsage.cost_usd || 0).toFixed(6)}
            </div>
          )}
        </div>
      )}

      {/* Raw Results (Collapsible) */}
      {previewResults && (
        <details style={{ marginTop: '20px' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '10px' }}>
            View Raw Results ({previewResults.results?.length || 0} classifications)
          </summary>
          <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '10px' }}>
            <pre style={{ fontSize: '11px', margin: 0, whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(previewResults, null, 2)}
            </pre>
          </div>
        </details>
      )}
    </div>
  )
}

export default PreviewExecutor
