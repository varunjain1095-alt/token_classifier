import React, { useState, useEffect, useMemo } from 'react'

interface TokenEstimate {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  model: string
  cached_input_tokens?: number
}

interface TokenRanges {
  low: TokenEstimate
  base: TokenEstimate
  high: TokenEstimate
  model: string
  breakdown?: {
    review_text_tokens: number
    review_text_tokens_total: number
    prompt_overhead_tokens: number
    prompt_overhead_tokens_total: number
    output_tokens: number
    output_tokens_total: number
    reviews_per_request: number
    total_requests: number
    review_text_status: 'exact' | 'estimated' | 'unavailable'
    output_status: string
    taxonomy_applied?: boolean
  }
}

interface PricingRecord {
  provider: string
  provider_name: string
  model_id: string
  display_name: string
  input_per_million: number | null
  cached_input_per_million: number | null
  output_per_million: number | null
  provider_fees: {
    request_fee_per_1k?: { low: number; medium: number; high: number }
    additional?: Record<string, number>
    description?: string
  } | null
  context_threshold_tokens: number | null
  service_tiers?: Record<string, string> | null
  batch?: { input_per_million: number; cached_input_per_million: number | null; output_per_million: number } | null
  status: 'active' | 'sunsetting' | 'deprecated' | 'limited'
  status_note?: string
  sunset_date?: string
  source_url: string
  effective_date: string | null
  last_verified_date?: string
}

interface ComparisonRow {
  provider: string
  provider_name: string
  requested_model_id?: string
  resolved_model_id?: string
  model_id: string
  display_name: string
  applied_rates?: {
    input_per_million: number
    cached_input_per_million: number | null
    output_per_million: number
  } | null
  input_cost: number
  cached_input_cost: number | null
  cached_input_supported: boolean
  output_cost: number
  provider_fee_cost: number
  provider_fees: PricingRecord['provider_fees']
  context_threshold_tokens: number | null
  tier_applied?: string
  service_tiers?: Record<string, string> | null
  batch?: PricingRecord['batch']
  per_request_cost: number
  workload_cost: number
  effective_date: string | null
  last_verified_date?: string
  source_url: string
  status: string
  status_note?: string
  sunset_date?: string
  tier_supported?: boolean
  error?: string
}

interface TokenEstimatorProps {
  experimentConfig?: any
  workloadSelection?: any
  previewRows?: any[]
  fieldMapping?: Record<string, string>
  fileId?: string
  onEstimateComplete: (estimate: any) => void
}

type SortKey = 'provider' | 'model' | 'input_cost' | 'output_cost' | 'workload_cost'
type ServiceTier = 'standard' | 'batch' | 'flex'

const PROVIDER_ORDER = ['openai', 'google', 'anthropic', 'perplexity']

const TokenEstimator: React.FC<TokenEstimatorProps> = ({
  experimentConfig,
  workloadSelection,
  previewRows,
  fieldMapping,
  fileId,
  onEstimateComplete
}) => {
  const [catalogue, setCatalogue] = useState<PricingRecord[]>([])
  const [previewModel, setPreviewModel] = useState<string>('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState<string>('')
  const [showDeprecated, setShowDeprecated] = useState<boolean>(false)
  const [pickerOpen, setPickerOpen] = useState<boolean>(false)
  const [tokenRanges, setTokenRanges] = useState<TokenRanges | null>(null)
  const [rows, setRows] = useState<ComparisonRow[]>([])
  const [serviceTier, setServiceTier] = useState<ServiceTier>('standard')
  const [sortKey, setSortKey] = useState<SortKey>('workload_cost')
  const [sortAsc, setSortAsc] = useState<boolean>(true)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Load the pricing catalogue and preview model once
  useEffect(() => {
    const loadCatalogue = async () => {
      try {
        const response = await fetch('/api/tokens/pricing-info', { credentials: 'include' })
        const data = await response.json()
        if (data.success) {
          const records: PricingRecord[] = data.pricing_info.records
          setCatalogue(records)
          const preview = data.pricing_info.preview_model || ''
          setPreviewModel(preview)
          // Default selection: preview model if catalogued, else first active record
          const initial = records.find(r => r.model_id === preview) ||
            records.find(r => r.status !== 'deprecated')
          if (initial) setSelectedIds(new Set([initial.model_id]))
        }
      } catch (e) {
        setError('Failed to load pricing catalogue')
      }
    }
    loadCatalogue()
  }, [])

  // Compute token ranges once (tiktoken baseline, independent of model choices)
  useEffect(() => {
    if (experimentConfig && workloadSelection && previewModel && !tokenRanges) {
      generateTokenRanges()
    }
  }, [experimentConfig, workloadSelection, previewModel])

  // Recalculate comparison whenever selection or token ranges change
  useEffect(() => {
    if (tokenRanges && selectedIds.size > 0) {
      generateComparison()
    } else if (selectedIds.size === 0) {
      setRows([])
    }
  }, [tokenRanges, selectedIds, serviceTier])

  // Representative review text: median-length review from the preview rows,
  // so the estimate reflects this dataset rather than a placeholder sentence.
  const representativeText = () => {
    if (!previewRows || previewRows.length === 0 || !fieldMapping) return ''
    const col = Object.keys(fieldMapping).find(h => fieldMapping[h] === 'review_text')
    if (!col) return ''
    const texts = previewRows
      .map(r => String(r?.[col] ?? ''))
      .filter(t => t.trim().length > 0)
    if (!texts.length) return ''
    texts.sort((a, b) => a.length - b.length)
    return texts[Math.floor(texts.length / 2)]
  }

  const generateTokenRanges = async () => {
    setLoading(true)
    setError(null)
    try {
      // Let the backend construct the real request (system prompt with
      // objective/taxonomy/schema + review text) rather than estimating a
      // synthetic payload.
      const tokenResponse = await fetch('/api/tokens/estimate-ranges', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          experiment_config: experimentConfig,
          review_text: representativeText() || 'This is a sample review text for token estimation.',
          file_id: fileId,
          field_mapping: fieldMapping || {},
          workload_selection: workloadSelection,
        }),
      })

      const tokenData = await tokenResponse.json()
      if (tokenData.success) {
        setTokenRanges(tokenData.token_ranges)
      } else {
        setError(tokenData.error || 'Failed to estimate tokens')
      }
    } catch (err) {
      setError('Estimation failed: ' + err)
    } finally {
      setLoading(false)
    }
  }

  const generateComparison = async () => {
    if (!tokenRanges || selectedIds.size === 0) return
    setLoading(true)
    setError(null)
    try {
      // Include the configured preview model so its cost continues downstream
      const ids = new Set(selectedIds)
      if (previewModel) ids.add(previewModel)

      // When review-text tokens were counted exactly across all selected
      // records, price the workload on the true per-request average so
      // workload_cost == exact token totals (not median x count).
      const bd = tokenRanges.breakdown
      const pricedEstimate =
        bd && bd.review_text_status === 'exact' && bd.total_requests > 0
          ? {
              ...tokenRanges.base,
              input_tokens: Math.round(
                (bd.review_text_tokens_total + bd.prompt_overhead_tokens_total) /
                  bd.total_requests),
            }
          : tokenRanges.base
      const requestCount = bd?.total_requests || workloadSelection?.count || 1

      const response = await fetch('/api/tokens/compare-costs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          token_estimate: pricedEstimate,
          request_count: requestCount,
          model_ids: Array.from(ids),
          service_tier: serviceTier,
        }),
      })

      const data = await response.json()
      if (data.success) {
        // Keep tier-unsupported rows so they render as "Not supported";
        // drop only unpriceable/unknown models
        const allRows: ComparisonRow[] = data.rows.filter(
          (r: ComparisonRow) => !r.error || r.tier_supported === false)
        setRows(allRows.filter(r => selectedIds.has(r.model_id)))

        const previewRow = allRows.find(r => r.model_id === previewModel)
        if (previewRow) {
          onEstimateComplete({
            tokenRanges,
            costEstimate: {
              input_cost: previewRow.input_cost,
              output_cost: previewRow.output_cost,
              cached_input_cost: previewRow.cached_input_cost,
              cached_input_supported: previewRow.cached_input_supported,
              provider_fee_cost: previewRow.provider_fee_cost,
              total_cost: previewRow.per_request_cost,
              model: previewModel,
              tokens: {
                input: pricedEstimate.input_tokens,
                output: tokenRanges.base.output_tokens,
                cached_input: tokenRanges.base.cached_input_tokens || 0,
                total: pricedEstimate.input_tokens + tokenRanges.base.output_tokens,
              }
            },
            workloadCost: {
              total_requests: data.request_count,
              total_cost: previewRow.workload_cost,
              model: previewModel,
              estimated_at: data.estimated_at,
            },
            comparisonModels: Array.from(selectedIds),
          })
        }
      }
    } catch (err) {
      setError('Estimation failed: ' + err)
    } finally {
      setLoading(false)
    }
  }

  const toggleModel = (modelId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(modelId)) next.delete(modelId)
      else next.add(modelId)
      return next
    })
  }

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc(!sortAsc)
    else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  const visibleCatalogue = useMemo(() => {
    const q = search.trim().toLowerCase()
    return catalogue
      .filter(r => showDeprecated || r.status !== 'deprecated')
      .filter(r => !q ||
        r.model_id.toLowerCase().includes(q) ||
        r.display_name.toLowerCase().includes(q) ||
        r.provider_name.toLowerCase().includes(q))
  }, [catalogue, search, showDeprecated])

  const grouped = useMemo(() => {
    const map = new Map<string, PricingRecord[]>()
    for (const r of visibleCatalogue) {
      if (!map.has(r.provider)) map.set(r.provider, [])
      map.get(r.provider)!.push(r)
    }
    return PROVIDER_ORDER.filter(p => map.has(p)).map(p => ({
      provider: p,
      providerName: map.get(p)![0].provider_name,
      records: map.get(p)!,
    }))
  }, [visibleCatalogue])

  const sortedRows = useMemo(() => {
    const copy = [...rows]
    copy.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'provider': cmp = a.provider_name.localeCompare(b.provider_name); break
        case 'model': cmp = a.display_name.localeCompare(b.display_name); break
        case 'input_cost': cmp = a.input_cost - b.input_cost; break
        case 'output_cost': cmp = a.output_cost - b.output_cost; break
        case 'workload_cost': cmp = a.workload_cost - b.workload_cost; break
      }
      return sortAsc ? cmp : -cmp
    })
    return copy
  }, [rows, sortKey, sortAsc])

  const hasNonOpenAI = rows.some(r => r.provider !== 'openai')

  const formatCurrency = (amount: number | null | undefined) => {
    if (amount === null || amount === undefined) return 'Not applicable'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 6
    }).format(amount)
  }

  const formatNumber = (num: number) => num.toLocaleString()

  const feeSummary = (r: ComparisonRow): string => {
    if (r.provider_fee_cost > 0) {
      const base = formatCurrency(r.provider_fee_cost)
      const extra = r.provider_fees?.additional
        ? '; ' + Object.entries(r.provider_fees.additional)
            .map(([k, v]) => `${k.replace(/_/g, ' ')} $${v}/1M`)
            .join(', ')
        : ''
      return base + extra
    }
    if (r.context_threshold_tokens) {
      return `Context tier > ${formatNumber(r.context_threshold_tokens)} tokens/request`
    }
    // Batch pricing is only shown when it is actually applied, never as a
    // silent discount on a Standard-tier row.
    if (r.service_tiers?.batch && r.tier_applied?.startsWith('batch')) {
      return `Batch: ${r.service_tiers.batch}`
    }
    return 'Not applicable'
  }

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortAsc ? ' ▲' : ' ▼') : ''

  const thStyle: React.CSSProperties = {
    textAlign: 'left',
    padding: '8px',
    borderBottom: '2px solid var(--border)',
    cursor: 'pointer',
    userSelect: 'none',
    whiteSpace: 'nowrap',
  }

  const tdStyle: React.CSSProperties = {
    padding: '8px',
    borderBottom: '1px solid var(--border)',
    verticalAlign: 'top',
  }

  if (loading && !tokenRanges) {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <div>Generating token and cost estimates...</div>
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
      <h3>Token &amp; Cost Estimation</h3>

      {/* Preview-model separation disclosure */}
      <div style={{
        padding: '10px',
        backgroundColor: 'var(--warning-soft)',
        border: '1px solid var(--warning)',
        borderRadius: 'var(--radius-sm)',
        marginBottom: '20px',
        fontSize: '13px',
        color: 'var(--warning)'
      }}>
        Selecting models here only compares estimated costs. Classification Preview
        runs using the configured OpenAI preview model{previewModel ? ` (${previewModel})` : ''}.
      </div>

      {/* Processing tier selection */}
      <div style={{ marginBottom: '15px', display: 'flex', gap: '15px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Processing Tier:
          </label>
          <select
            value={serviceTier}
            onChange={(e) => setServiceTier(e.target.value as ServiceTier)}
            style={{ padding: '8px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', minWidth: '180px' }}
          >
            <option value="standard">Standard / synchronous</option>
            <option value="batch">Batch</option>
            <option value="flex">Flex</option>
          </select>
        </div>
      </div>

      {/* Searchable multi-select model picker */}
      <div style={{ marginBottom: '15px' }}>
        <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
          Compare Models ({selectedIds.size} selected):
        </label>
        <div style={{
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          padding: '10px',
          backgroundColor: 'var(--surface-2)'
        }}>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              type="text"
              placeholder="Search models..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPickerOpen(true) }}
              onFocus={() => setPickerOpen(true)}
              style={{ padding: '8px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', minWidth: '240px' }}
            />
            <label style={{ fontSize: '13px', color: 'var(--text-2)' }}>
              <input
                type="checkbox"
                checked={showDeprecated}
                onChange={(e) => setShowDeprecated(e.target.checked)}
                style={{ marginRight: '5px' }}
              />
              Show deprecated models
            </label>
            <button
              onClick={() => setPickerOpen(!pickerOpen)}
              style={{ padding: '6px 12px', fontSize: '12px' }}
            >
              {pickerOpen ? 'Hide list' : 'Show list'}
            </button>
            {loading && <span style={{ fontSize: '13px', color: 'var(--text-2)' }}>Recalculating…</span>}
          </div>

          {pickerOpen && (
            <div style={{
              maxHeight: '260px',
              overflowY: 'auto',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--surface)',
              padding: '8px'
            }}>
              {grouped.map(g => (
                <div key={g.provider} style={{ marginBottom: '10px' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '12px', color: 'var(--text-2)', marginBottom: '4px', textTransform: 'uppercase' }}>
                    {g.providerName}
                  </div>
                  {g.records.map(r => (
                    <label
                      key={r.model_id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '4px 6px',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        fontSize: '13px',
                        backgroundColor: selectedIds.has(r.model_id) ? 'var(--info-soft)' : 'transparent',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.has(r.model_id)}
                        onChange={() => toggleModel(r.model_id)}
                        style={{ marginRight: '8px' }}
                      />
                      <span>
                        {r.display_name} <span style={{ color: 'var(--text-2)' }}>({r.model_id})</span>
                        {r.status === 'deprecated' && (
                          <span style={{ marginLeft: '6px', color: 'var(--danger)', fontSize: '11px' }}>deprecated</span>
                        )}
                        {r.status === 'sunsetting' && (
                          <span style={{ marginLeft: '6px', color: 'var(--warning)', fontSize: '11px' }}>
                            sunsets {r.sunset_date}
                          </span>
                        )}
                      </span>
                    </label>
                  ))}
                </div>
              ))}
              {grouped.length === 0 && (
                <div style={{ fontSize: '13px', color: 'var(--text-2)', padding: '8px' }}>No models match.</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Approximate-tokenization label for non-OpenAI selections */}
      {hasNonOpenAI && (
        <div style={{
          padding: '10px',
          backgroundColor: 'var(--info-soft)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '20px',
          fontSize: '13px',
          color: 'var(--info)'
        }}>
          Approximate estimates: token counts use the tiktoken baseline; non-OpenAI
          providers' native tokenization may differ.
        </div>
      )}

      {/* Migration warning for sunsetting models */}
      {rows.some(r => r.status === 'sunsetting') && (
        <div style={{
          padding: '10px',
          backgroundColor: 'var(--warning-soft)',
          border: '1px solid var(--warning)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '20px',
          fontSize: '13px',
          color: 'var(--warning)'
        }}>
          Migration warning: Perplexity Sonar Chat Completions is moving to the Agent API
          and is supported until {rows.find(r => r.status === 'sunsetting')?.sunset_date || 'the announced sunset date'}.
          These models remain operational but should be migrated before then.
        </div>
      )}

      {tokenRanges && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Token Estimates (tiktoken baseline)</h4>

          {/* Per-request construction, priced against the fully built request */}
          {tokenRanges.breakdown && (
            <div className="card" style={{ marginBottom: '15px', padding: '15px' }}>
              <div style={{ fontWeight: 'bold', marginBottom: '10px' }}>Per-request construction</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(175px, 1fr))', gap: '12px', fontSize: '14px' }}>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--info)', fontSize: '18px' }}>
                    {formatNumber(tokenRanges.breakdown.review_text_tokens)}
                    <span style={{ fontSize: '13px', color: 'var(--text-2)', fontWeight: 500 }}> /req</span>
                  </div>
                  <div style={{ fontWeight: 700, color: 'var(--text)', fontSize: '14px' }}>
                    {formatNumber(tokenRanges.breakdown.review_text_tokens_total)} total
                    <span className={`chip ${tokenRanges.breakdown.review_text_status === 'exact' ? 'chip-success' : 'chip-warning'}`} style={{ marginLeft: '6px', fontSize: '11px' }}>
                      {tokenRanges.breakdown.review_text_status}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Review-text tokens</div>
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--info)', fontSize: '18px' }}>
                    {formatNumber(tokenRanges.breakdown.prompt_overhead_tokens)}
                    <span style={{ fontSize: '13px', color: 'var(--text-2)', fontWeight: 500 }}> /req</span>
                  </div>
                  <div style={{ fontWeight: 700, color: 'var(--text)', fontSize: '14px' }}>
                    {formatNumber(tokenRanges.breakdown.prompt_overhead_tokens_total)} total
                    <span className="chip chip-success" style={{ marginLeft: '6px', fontSize: '11px' }}>exact</span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                    Shared prompt / taxonomy / schema
                    {tokenRanges.breakdown.taxonomy_applied === false && ' (no taxonomy yet)'}
                  </div>
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--info)', fontSize: '18px' }}>
                    {formatNumber(tokenRanges.breakdown.output_tokens)}
                    <span style={{ fontSize: '13px', color: 'var(--text-2)', fontWeight: 500 }}> /req</span>
                  </div>
                  <div style={{ fontWeight: 700, color: 'var(--text)', fontSize: '14px' }}>
                    {formatNumber(tokenRanges.breakdown.output_tokens_total)} total
                    <span className="chip chip-warning" style={{ marginLeft: '6px', fontSize: '11px' }}>estimated</span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Output tokens</div>
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--text)', fontSize: '18px' }}>
                    {tokenRanges.breakdown.reviews_per_request}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Reviews per request (assumed)</div>
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--text)', fontSize: '18px' }}>
                    {formatNumber(tokenRanges.breakdown.total_requests || workloadSelection?.count || 1)}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>Total requests (= workload size)</div>
                </div>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '10px' }}>
                Assumption: 1 review per API request. Preview and full execution send one request per record.
                Review-text tokens are counted exactly across every selected stored record;
                output tokens are estimated from the configured max_tokens.
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
            <div style={{ padding: '15px', backgroundColor: 'var(--info-soft)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontWeight: 'bold', color: 'var(--info)' }}>Low Estimate</div>
              <div>Input: {formatNumber(tokenRanges.low.input_tokens)}</div>
              <div>Output: {formatNumber(tokenRanges.low.output_tokens)}</div>
              <div style={{ fontWeight: 'bold', marginTop: '5px' }}>
                Total: {formatNumber(tokenRanges.low.total_tokens)}
              </div>
            </div>

            <div style={{ padding: '15px', backgroundColor: 'var(--success-soft)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontWeight: 'bold', color: 'var(--success)' }}>Base Estimate</div>
              <div>Input: {formatNumber(tokenRanges.base.input_tokens)}</div>
              <div>Output: {formatNumber(tokenRanges.base.output_tokens)}</div>
              <div style={{ fontWeight: 'bold', marginTop: '5px' }}>
                Total: {formatNumber(tokenRanges.base.total_tokens)}
              </div>
            </div>

            <div style={{ padding: '15px', backgroundColor: 'var(--warning-soft)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontWeight: 'bold', color: 'var(--warning)' }}>High Estimate</div>
              <div>Input: {formatNumber(tokenRanges.high.input_tokens)}</div>
              <div>Output: {formatNumber(tokenRanges.high.output_tokens)}</div>
              <div style={{ fontWeight: 'bold', marginTop: '5px' }}>
                Total: {formatNumber(tokenRanges.high.total_tokens)}
              </div>
            </div>
          </div>
        </div>
      )}

      {sortedRows.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h4>Model Cost Comparison ({formatNumber(tokenRanges?.breakdown?.total_requests || workloadSelection?.count || 1)} requests · {serviceTier} tier)</h4>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr>
                  <th style={thStyle} onClick={() => toggleSort('provider')}>
                    Provider{sortIndicator('provider')}
                  </th>
                  <th style={thStyle} onClick={() => toggleSort('model')}>
                    Model{sortIndicator('model')}
                  </th>
                  <th style={{ ...thStyle, cursor: 'default' }}>Tier</th>
                  <th style={thStyle} onClick={() => toggleSort('input_cost')}>
                    Input Cost{sortIndicator('input_cost')}
                  </th>
                  <th style={{ ...thStyle, cursor: 'default' }}>Cached Input</th>
                  <th style={thStyle} onClick={() => toggleSort('output_cost')}>
                    Output Cost{sortIndicator('output_cost')}
                  </th>
                  <th style={{ ...thStyle, cursor: 'default' }}>Other Costs</th>
                  <th style={{ ...thStyle, cursor: 'default' }}>Per Request</th>
                  <th style={thStyle} onClick={() => toggleSort('workload_cost')}>
                    Workload Cost{sortIndicator('workload_cost')}
                  </th>
                  <th style={{ ...thStyle, cursor: 'default' }}>Verified</th>
                  <th style={{ ...thStyle, cursor: 'default' }}>Source</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map(r => (
                  <tr key={r.model_id} style={{ opacity: r.status === 'deprecated' ? 0.65 : 1 }}>
                    <td style={tdStyle}>{r.provider_name}</td>
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 'bold' }}>{r.display_name}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-2)' }}>{r.model_id}</div>
                      {r.resolved_model_id && r.requested_model_id && r.resolved_model_id !== r.requested_model_id && (
                        <div style={{ fontSize: '11px', color: 'var(--danger)' }}>
                          resolved to {r.resolved_model_id}
                        </div>
                      )}
                      {r.applied_rates && (
                        <div style={{ fontSize: '11px', color: 'var(--text-2)' }}>
                          in ${r.applied_rates.input_per_million}/1M · out ${r.applied_rates.output_per_million}/1M
                          {r.applied_rates.cached_input_per_million !== null && ` · cached $${r.applied_rates.cached_input_per_million}/1M`}
                        </div>
                      )}
                      {r.status === 'sunsetting' && (
                        <div style={{ fontSize: '11px', color: 'var(--warning)' }}>
                          sunsets {r.sunset_date}
                        </div>
                      )}
                    </td>
                    {r.tier_supported === false ? (
                      <>
                        <td style={tdStyle}>Not supported</td>
                        <td style={tdStyle}>Not supported</td>
                        <td style={tdStyle}>Not supported</td>
                        <td style={tdStyle}>Not supported</td>
                        <td style={{ ...tdStyle, fontSize: '11px', color: 'var(--text-2)' }}>
                          {serviceTier} tier unavailable{Array.isArray((r as any).supported_tiers) ? ` (supports: ${(r as any).supported_tiers.join(', ')})` : ''}
                        </td>
                        <td style={tdStyle}>Not supported</td>
                        <td style={tdStyle}>Not supported</td>
                      </>
                    ) : (
                      <>
                        <td style={tdStyle}>{r.tier_applied || 'standard'}</td>
                        <td style={tdStyle}>{formatCurrency(r.input_cost)}</td>
                        <td style={tdStyle}>{r.cached_input_supported ? formatCurrency(r.cached_input_cost) : 'Not applicable'}</td>
                        <td style={tdStyle}>{formatCurrency(r.output_cost)}</td>
                        <td style={{ ...tdStyle, fontSize: '11px', color: 'var(--text-2)' }}>{feeSummary(r)}</td>
                        <td style={{ ...tdStyle, fontWeight: 'bold' }}>{formatCurrency(r.per_request_cost)}</td>
                        <td style={{ ...tdStyle, fontWeight: 'bold' }}>{formatCurrency(r.workload_cost)}</td>
                      </>
                    )}
                    <td style={tdStyle}>{r.effective_date || r.last_verified_date || '-'}</td>
                    <td style={tdStyle}>
                      <a href={r.source_url} target="_blank" rel="noreferrer">Pricing</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-2)' }}>
            All models priced with the same workload ({formatNumber(workloadSelection?.count || 1)} requests),
            token estimate, batching and cache assumptions. Unsupported pricing dimensions
            show as "Not applicable".
          </div>
        </div>
      )}
    </div>
  )
}

export default TokenEstimator
