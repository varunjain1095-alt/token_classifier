import { useState, useEffect, Fragment } from 'react'
import { AuthProvider } from './context/AuthContext'
import SessionIndicator from './components/SessionIndicator'
import FileUpload from './components/FileUpload'
import FilePreview from './components/FilePreview'
import ImportDiagnostics from './components/ImportDiagnostics'
import DatabaseConnection from './components/DatabaseConnection'
import SchemaBrowser from './components/SchemaBrowser'
import FieldMapper from './components/FieldMapper'
import WorkloadSelector from './components/WorkloadSelector'
import CategoryManager from './components/CategoryManager'
import ExperimentConfig from './components/ExperimentConfig'
import UndefinedClassificationConfig from './components/UndefinedClassificationConfig'
import TokenEstimator from './components/TokenEstimator'
import SampleSelector from './components/SampleSelector'
import ExpectationsManager from './components/ExpectationsManager'
import PreviewExecutor from './components/PreviewExecutor'
import ResultsAnalyzer from './components/ResultsAnalyzer'
import CategoryDiscovery from './components/CategoryDiscovery'
import RecommendationsPanel from './components/RecommendationsPanel'
import ClassificationExecutor from './components/ClassificationExecutor'
import ExportManager from './components/ExportManager'
import { ThemeToggle } from './components/ui'
import './App.css'

interface DatabaseInfo {
  host: string
  port: number
  database: string
  username: string
}

interface FieldMapping {
  [key: string]: string
}

interface WorkloadSelection {
  mode: string
  count: number
  specificRows: string[]
  seed: number
  totalEligible: number
}

interface CategorySet {
  id: string
  name: string
  description: string
  categories: any[]
  version: number
  is_active: boolean
}

interface ExperimentConfig {
  id: string
  name: string
  description: string
  config: any
  version: number
  is_active: boolean
}

function App() {
  const [status, setStatus] = useState<string>('Loading...')
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme')
    return saved === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])
  const [activeTab, setActiveTab] = useState<'upload' | 'database' | 'mapping' | 'workload' | 'configuration' | 'estimation' | 'sampling' | 'preview' | 'results' | 'discovery' | 'recommendations' | 'execution' | 'export'>('upload')
  const [uploadedFile, setUploadedFile] = useState<any>(null)
  const [fieldMapping, setFieldMapping] = useState<FieldMapping>({})
  const [workloadSelection, setWorkloadSelection] = useState<WorkloadSelection | null>(null)
  const [totalEligible, setTotalEligible] = useState<number>(0)
  const [eligibilityInfo, setEligibilityInfo] = useState<any>(null)
  const [rowIndex, setRowIndex] = useState<any>(null)
  const [mappingValid, setMappingValid] = useState<boolean>(false)
  const [workloadValid, setWorkloadValid] = useState<boolean>(false)
  const [selectedCategorySet, setSelectedCategorySet] = useState<CategorySet | null>(null)
  const [selectedExperimentConfig, setSelectedExperimentConfig] = useState<ExperimentConfig | null>(null)
  const [classificationMode, setClassificationMode] = useState<'defined' | 'undefined'>('defined')
  const [tokenEstimate, setTokenEstimate] = useState<any>(null)
  const [selectedSample, setSelectedSample] = useState<any>(null)
  const [expectations, setExpectations] = useState<any>(null)
  const [previewResults, setPreviewResults] = useState<any>(null)
  const [analysisResults, setAnalysisResults] = useState<any>(null)
  const [discoveryResults, setDiscoveryResults] = useState<any>(null)
  const [recommendations, setRecommendations] = useState<any>(null)
  const [executionResults, setExecutionResults] = useState<any>(null)
  const [apiKey, setApiKey] = useState<string>('')
  const [exportData, setExportData] = useState<any>(null)
  const [projectStateLoaded, setProjectStateLoaded] = useState<boolean>(false)
  const [fileUploadedThisSession, setFileUploadedThisSession] = useState<boolean>(false)

  useEffect(() => {
    fetch('/api/health')
      .then(response => response.json())
      .then(data => {
        setStatus(`Backend Status: ${data.status} - ${data.service || 'Ready'}`)
        setError(null)
      })
      .catch(err => {
        setError(`Connection failed: ${err.message}`)
        setStatus('Error connecting to backend')
      })

    // Restore persisted wizard state so refresh keeps dataset ID,
    // mapping, workload selection and progress.
    fetch('/api/session/project-state', { credentials: 'include' })
      .then(response => response.ok ? response.json() : null)
      .then(data => {
        const state = data?.project_state
        if (state && state.uploadedFile?.file_id) {
          setUploadedFile(state.uploadedFile)
          setFieldMapping(state.fieldMapping || {})
          setWorkloadSelection(state.workloadSelection || null)
          setTotalEligible(state.totalEligible || 0)
          setEligibilityInfo(state.eligibilityInfo || null)
          setRowIndex(state.rowIndex || null)
          setMappingValid(!!state.mappingValid)
          setWorkloadValid(!!state.workloadValid)
          setSelectedCategorySet(state.selectedCategorySet || null)
          setSelectedExperimentConfig(state.selectedExperimentConfig || null)
          setClassificationMode(state.classificationMode || 'defined')
          setTokenEstimate(state.tokenEstimate || null)
          setSelectedSample(state.selectedSample || null)
          // Always land on Upload after refresh — restored state keeps the
          // later tabs enabled so the user can click forward.
        }
      })
      .catch(() => {})
      .finally(() => setProjectStateLoaded(true))
  }, [])

  // Persist wizard state to the session whenever it advances.
  useEffect(() => {
    if (!projectStateLoaded || !uploadedFile?.file_id) return
    fetch('/api/session/project-state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        project_state: {
          uploadedFile,
          fieldMapping,
          workloadSelection,
          totalEligible,
          eligibilityInfo,
          rowIndex,
          mappingValid,
          workloadValid,
          selectedCategorySet,
          selectedExperimentConfig,
          classificationMode,
          tokenEstimate,
          selectedSample
        }
      })
    }).catch(() => {})
  }, [projectStateLoaded, uploadedFile, fieldMapping, workloadSelection,
      totalEligible, eligibilityInfo, rowIndex, mappingValid, workloadValid,
      selectedCategorySet, selectedExperimentConfig, classificationMode,
      tokenEstimate, selectedSample])

  const handleFileUpload = (fileData: any) => {
    setUploadedFile(fileData)
    setFileUploadedThisSession(true)
    // Auto-switch to mapping tab after upload
    if (fileData.parse_result?.success) {
      setActiveTab('mapping')
    }
  }

  const handleMappingComplete = async (mapping: FieldMapping, rowIndexData?: any) => {
    setFieldMapping(mapping)
    setMappingValid(true)
    setRowIndex(rowIndexData || null)
    // Eligible count comes from the backend over the complete stored
    // snapshot (blank rows excluded), never from preview_rows.
    try {
      const response = await fetch('/api/eligibility/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          file_id: uploadedFile?.file_id,
          field_mapping: mapping
        })
      })
      const data = await response.json()
      const result = data?.screening_result
      if (result) {
        setTotalEligible(result.eligible_records ?? 0)
        setEligibilityInfo({
          loaded: result.loaded_physical_rows ?? result.total_records ?? 0,
          eligible: result.eligible_records ?? 0,
          excluded: result.blank_rows_excluded ?? result.excluded_records ?? 0
        })
      } else if (uploadedFile?.parse_result?.total_rows) {
        setTotalEligible(uploadedFile.parse_result.total_rows)
      }
    } catch {
      if (uploadedFile?.parse_result?.total_rows) {
        setTotalEligible(uploadedFile.parse_result.total_rows)
      }
    }
    // Auto-switch to workload tab
    setActiveTab('workload')
  }

  const handleMappingChange = (mapping: FieldMapping) => {
    setFieldMapping(mapping)
  }

  const handleWorkloadSelect = (selection: WorkloadSelection) => {
    setWorkloadSelection(selection)
    // Auto-switch to configuration tab
    setActiveTab('configuration')
  }

  const handleWorkloadValidation = (validation: any) => {
    setWorkloadValid(validation.valid)
  }

  const steps: { key: string, label: string, disabled: boolean, done: boolean }[] = [
    { key: 'upload', label: 'File Upload', disabled: false, done: !!uploadedFile },
    { key: 'database', label: 'Database', disabled: false, done: false },
    { key: 'mapping', label: 'Field Mapping', disabled: !uploadedFile, done: mappingValid },
    { key: 'workload', label: 'Workload', disabled: !mappingValid, done: workloadValid },
    { key: 'configuration', label: 'Configuration', disabled: !workloadValid, done: !!selectedExperimentConfig },
    { key: 'estimation', label: 'Token & Cost', disabled: !selectedExperimentConfig, done: !!tokenEstimate },
    { key: 'sampling', label: 'Sampling', disabled: !tokenEstimate, done: !!selectedSample },
    { key: 'preview', label: 'Preview', disabled: !expectations, done: !!previewResults },
    { key: 'results', label: 'Results', disabled: !previewResults, done: !!analysisResults },
    { key: 'discovery', label: 'Discovery', disabled: !analysisResults, done: !!discoveryResults },
    { key: 'recommendations', label: 'Recommendations', disabled: !discoveryResults, done: !!recommendations },
    { key: 'execution', label: 'Execute', disabled: !recommendations, done: !!executionResults },
    { key: 'export', label: 'Export', disabled: !executionResults, done: !!exportData }
  ]

  return (
    <AuthProvider>
      <div className="App">
        <div className="ambient" aria-hidden="true">
          <div className="blob blob-1" />
          <div className="blob blob-2" />
          <div className="blob blob-3" />
        </div>
        <header className="topbar">
          <div className="brand">Review Classification Workbench</div>
          <div className="status-text">{status}</div>
          {error && <div className="error-text">{error}</div>}
          <SessionIndicator />
          <ThemeToggle
            theme={theme}
            onToggle={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}
          />
        </header>

        <main>
          {/* Step Navigation */}
          <div className="stepper">
            {steps.map((step, i) => (
              <Fragment key={step.key}>
                {i > 0 && (
                  <div className={`step-connector ${steps[i - 1].done ? 'done' : ''}`} />
                )}
                <button
                  className={`step ${activeTab === step.key ? 'active' : ''} ${step.done ? 'done' : ''}`}
                  onClick={() => setActiveTab(step.key as any)}
                  disabled={step.disabled}
                  title={step.label}
                  aria-label={`${step.label}${step.done ? ' (completed)' : step.disabled ? ' (locked)' : ''}`}
                  aria-current={activeTab === step.key ? 'step' : undefined}
                >
                  <div className="step-circle">
                    {step.done ? '✓' : i + 1}
                  </div>
                  <div className="step-label">{step.label}</div>
                </button>
              </Fragment>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === 'upload' && (
            <div>
              <FileUpload 
                onUploadComplete={handleFileUpload} 
                onUploadError={setError}
              />
              {uploadedFile && fileUploadedThisSession && (
                <div>
                  <FilePreview parseResult={uploadedFile.parse_result} />
                  <ImportDiagnostics diagnostics={uploadedFile.diagnostics} />
                </div>
              )}
              {/* Restored session files render nothing here — downstream
                  state stays intact, but Upload only shows content for a
                  file uploaded in this session. */}
            </div>
          )}
          
          {activeTab === 'database' && (
            <div>
              <DatabaseConnection onConnectionSuccess={(dbInfo: DatabaseInfo) => console.log('Database connected:', dbInfo)} />
              <SchemaBrowser connectionInfo={{ host: 'localhost', port: 5432, database: 'review_classification', username: 'postgres' }} />
            </div>
          )}
          
          {activeTab === 'mapping' && uploadedFile && (
            <div>
              <FieldMapper 
                headers={uploadedFile.parse_result?.headers || []}
                sampleData={uploadedFile.parse_result?.preview_rows || []}
                onMappingComplete={handleMappingComplete}
                onMappingChange={handleMappingChange}
              />
            </div>
          )}
          
          {activeTab === 'workload' && mappingValid && (
            <div>
              <WorkloadSelector 
                totalEligible={totalEligible}
                eligibilityInfo={eligibilityInfo}
                fileId={uploadedFile?.file_id}
                fieldMapping={fieldMapping}
                useColumnIds={rowIndex?.mode !== 'generated'}
                onWorkloadSelect={handleWorkloadSelect}
                onValidationChange={handleWorkloadValidation}
              />
            </div>
          )}
          
          {activeTab === 'configuration' && workloadValid && (
            <div>
              {/* Classification Mode */}
              <div style={{ marginBottom: '25px' }}>
                <h3>Classification Mode</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
                  {[
                    { value: 'defined', label: 'I already have categories', description: 'Select or create category sets with definitions, examples and classification rules.' },
                    { value: 'undefined', label: "I don't know my categories yet", description: 'State your objective — the preview model will propose draft categories for review.' }
                  ].map(mode => (
                    <button
                      key={mode.value}
                      onClick={() => {
                        setClassificationMode(mode.value as 'defined' | 'undefined')
                        // Clear stale selections from the other mode
                        setSelectedCategorySet(null)
                        setSelectedExperimentConfig(null)
                      }}
                      style={{
                        padding: '15px',
                        backgroundColor: classificationMode === mode.value ? 'var(--primary)' : 'var(--surface-2)',
                        color: classificationMode === mode.value ? 'var(--on-primary)' : 'var(--text)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>{mode.label}</div>
                      <div style={{ fontSize: '12px', opacity: 0.85 }}>{mode.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              {classificationMode === 'defined' ? (
                <div>
                  <div style={{ marginBottom: '30px' }}>
                    <CategoryManager onCategorySetSelect={setSelectedCategorySet} />
                  </div>
                  
                  <div>
                    <ExperimentConfig 
                      categorySetId={selectedCategorySet?.id}
                      onConfigSelect={setSelectedExperimentConfig}
                    />
                  </div>
                </div>
              ) : (
                <UndefinedClassificationConfig 
                  onConfigSelect={(config) => {
                    setSelectedExperimentConfig(config)
                    setActiveTab('estimation')
                  }}
                />
              )}
            </div>
          )}
          
          {activeTab === 'estimation' && selectedExperimentConfig && (
            <div>
              <TokenEstimator
                experimentConfig={selectedExperimentConfig}
                workloadSelection={workloadSelection}
                previewRows={uploadedFile?.parse_result?.preview_rows || []}
                fieldMapping={fieldMapping}
                fileId={uploadedFile?.file_id}
                onEstimateComplete={setTokenEstimate}
              />
            </div>
          )}
          
          {activeTab === 'sampling' && tokenEstimate && (
            <div>
              <div style={{ marginBottom: '30px' }}>
                <SampleSelector
                  fileId={uploadedFile?.file_id}
                  fieldMapping={fieldMapping}
                  useColumnIds={rowIndex?.mode !== 'generated'}
                  workloadSelection={workloadSelection}
                  totalEligible={totalEligible}
                  onSampleSelect={setSelectedSample}
                  onValidationChange={(validation) => console.log('Sample validation:', validation)}
                />
              </div>
              
              {selectedSample && (
                <div>
                  <ExpectationsManager
                    sampleRecords={selectedSample.sample_records || []}
                    classificationMode={classificationMode}
                    categorySet={selectedCategorySet}
                    onExpectationsComplete={(result) => {
                      setExpectations(result)
                      setActiveTab('preview')
                    }}
                  />
                </div>
              )}
            </div>
          )}
          
          {activeTab === 'preview' && expectations && (
            <div>
              <PreviewExecutor 
                sampleRecords={selectedSample?.sample_records || []}
                experimentConfig={selectedExperimentConfig}
                expectations={expectations?.expectations || []}
                onPreviewComplete={setPreviewResults}
              />
            </div>
          )}
          
          {activeTab === 'results' && previewResults && (
            <div>
              <ResultsAnalyzer
                previewResults={previewResults}
                expectations={expectations?.expectations || []}
                sampleRecords={selectedSample?.sample_records || []}
                onAnalysisComplete={setAnalysisResults}
              />
            </div>
          )}
          
          {activeTab === 'discovery' && analysisResults && (
            <div>
              <CategoryDiscovery 
                sampleRecords={selectedSample?.sample_records || []}
                onDiscoveryComplete={setDiscoveryResults}
              />
            </div>
          )}
          
          {activeTab === 'recommendations' && discoveryResults && (
            <div>
              <RecommendationsPanel
                analysisResults={analysisResults}
                discoveryResults={discoveryResults}
                currentConfig={selectedExperimentConfig}
                costEstimate={tokenEstimate}
                previewResults={previewResults}
                onRecommendationsComplete={setRecommendations}
              />
            </div>
          )}
          
          {activeTab === 'execution' && recommendations && (
            <div>
              <ClassificationExecutor 
                datasetRecords={uploadedFile?.parse_result?.data || []}
                experimentConfig={selectedExperimentConfig}
                categorySet={discoveryResults}
                apiKey={apiKey}
                estimatedCost={tokenEstimate?.workloadCost?.total_cost || 0}
                onExecutionComplete={setExecutionResults}
              />
            </div>
          )}
          
          {activeTab === 'export' && executionResults && (
            <div>
              <ExportManager 
                executionResults={executionResults}
                onExportComplete={setExportData}
              />
            </div>
          )}

          {/* Summary Section */}
          {uploadedFile && mappingValid && workloadSelection && selectedExperimentConfig && tokenEstimate && selectedSample && expectations && previewResults && analysisResults && discoveryResults && recommendations && executionResults && exportData && (
            <div style={{ 
              marginTop: '30px', 
              padding: '20px', 
              backgroundColor: 'var(--success-soft)',
              borderRadius: 'var(--radius)',
              border: '1px solid var(--success)'
            }}>
              <h3>🎯 Ready for Classification</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
                <div>
                  <strong>File:</strong> {uploadedFile.filename}
                </div>
                <div>
                  <strong>Records:</strong> {uploadedFile.parse_result?.total_rows || 0}
                </div>
                <div>
                  <strong>Eligible:</strong> {totalEligible}
                </div>
                <div>
                  <strong>Selected:</strong> {workloadSelection.count}
                </div>
                <div>
                  <strong>Mode:</strong> {workloadSelection.mode}
                </div>
                <div>
                  <strong>Seed:</strong> {workloadSelection.seed}
                </div>
                <div>
                  <strong>Config:</strong> {selectedExperimentConfig?.name}
                </div>
                <div>
                  <strong>Categories:</strong> {selectedCategorySet?.categories.length || 0}
                </div>
                <div>
                  <strong>Est. Tokens:</strong> {tokenEstimate?.tokenRanges?.base?.total_tokens?.toLocaleString() || 0}
                </div>
                <div>
                  <strong>Est. Cost:</strong> ${tokenEstimate?.workloadCost?.total_cost?.toFixed(6) || '0.000000'}
                </div>
                <div>
                  <strong>Sample Size:</strong> {selectedSample?.sample_size || 0}
                </div>
                <div>
                  <strong>Expectations:</strong> {expectations?.expectations?.length || 0}
                </div>
                <div>
                  <strong>Accuracy:</strong> {analysisResults?.analysis?.accuracy?.overall_accuracy?.toFixed(1) || 0}%
                </div>
                <div>
                  <strong>Recommendations:</strong> {analysisResults?.recalibration?.recommendations?.length || 0}
                </div>
                <div>
                  <strong>Categories:</strong> {discoveryResults?.discovered_categories?.length || 0}
                </div>
                <div>
                  <strong>Recommendations:</strong> {recommendations?.summary?.total_recommendations || 0}
                </div>
                <div>
                  <strong>Health Score:</strong> {recommendations?.summary?.overall_health_score?.toFixed(0) || 0}
                </div>
                <div>
                  <strong>Execution:</strong> {executionResults?.status || 'Not started'}
                </div>
                <div>
                  <strong>Processed:</strong> {executionResults?.processed_records || 0}/{executionResults?.total_records || 0}
                </div>
                <div>
                  <strong>Exports:</strong> {exportData?.length || 0}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </AuthProvider>
  )
}

export default App
