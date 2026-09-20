import React, { useState } from 'react'

interface TableInfo {
  schema: string
  name: string
  type: string
  columns: Array<{
    name: string
    data_type: string
    is_nullable: boolean
    is_primary_key: boolean
  }>
  estimated_rows?: number
}

interface SchemaBrowserProps {
  connectionParams: any
  onTableSelect: (table: TableInfo) => void
}

const SchemaBrowser: React.FC<SchemaBrowserProps> = ({ 
  connectionParams, 
  onTableSelect 
}) => {
  const [schemas, setSchemas] = useState<string[]>([])
  const [selectedSchema, setSelectedSchema] = useState<string>('')
  const [tables, setTables] = useState<TableInfo[]>([])
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const loadSchemas = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/database/schemas', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          adapter_type: 'postgresql',
          connection_params: connectionParams
        }),
      })

      const result = await response.json()
      if (result.success) {
        setSchemas(result.schemas)
        if (result.schemas.length > 0) {
          setSelectedSchema(result.schemas[0])
          loadTables(result.schemas[0])
        }
      }
    } catch (error) {
      console.error('Failed to load schemas:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadTables = async (schema: string) => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/database/tables', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          adapter_type: 'postgresql',
          connection_params: connectionParams,
          schema: schema
        }),
      })

      const result = await response.json()
      if (result.success) {
        setTables(result.tables)
      }
    } catch (error) {
      console.error('Failed to load tables:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSchemaChange = (schema: string) => {
    setSelectedSchema(schema)
    setTables([])
    setSelectedTable(null)
    loadTables(schema)
  }

  const handleTableSelect = (table: TableInfo) => {
    setSelectedTable(table)
    onTableSelect(table)
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Schema Browser</h3>
      
      <div style={{ display: 'flex', gap: '20px' }}>
        {/* Schema Selection */}
        <div style={{ flex: '0 0 200px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
            Schema:
          </label>
          <select
            value={selectedSchema}
            onChange={(e) => handleSchemaChange(e.target.value)}
            style={{ 
              width: '100%', 
              padding: '8px', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--radius-sm)' 
            }}
          >
            <option value="">Select Schema</option>
            {schemas.map(schema => (
              <option key={schema} value={schema}>{schema}</option>
            ))}
          </select>
          
          <button
            onClick={loadSchemas}
            disabled={isLoading}
            style={{ 
              marginTop: '10px',
              padding: '8px 16px',
              backgroundColor: 'var(--primary)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              width: '100%'
            }}
          >
            {isLoading ? 'Loading...' : 'Refresh Schemas'}
          </button>
        </div>

        {/* Tables List */}
        <div style={{ flex: '1' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
            Tables ({tables.length}):
          </label>
          
          {isLoading ? (
            <div>Loading tables...</div>
          ) : (
            <div style={{ 
              maxHeight: '300px', 
              overflowY: 'auto', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--radius-sm)' 
            }}>
              {tables.map(table => (
                <div
                  key={`${table.schema}.${table.name}`}
                  onClick={() => handleTableSelect(table)}
                  style={{ 
                    padding: '10px', 
                    borderBottom: '1px solid var(--border)',
                    cursor: 'pointer',
                    backgroundColor: selectedTable?.name === table.name ? 'var(--info-soft)' : 'white'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>{table.name}</strong>
                      <span style={{ 
                        marginLeft: '10px', 
                        fontSize: '12px', 
                        color: 'var(--text-2)',
                        backgroundColor: table.type === 'view' ? 'var(--warning-soft)' : 'var(--success-soft)',
                        padding: '2px 6px',
                        borderRadius: 'var(--radius-sm)'
                      }}>
                        {table.type}
                      </span>
                    </div>
                    {table.estimated_rows && (
                      <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                        ~{table.estimated_rows.toLocaleString()} rows
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-2)', marginTop: '5px' }}>
                    {table.columns.length} columns
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Selected Table Details */}
      {selectedTable && (
        <div style={{ marginTop: '20px' }}>
          <h4>Table Details: {selectedTable.name}</h4>
          <div style={{ 
            backgroundColor: 'var(--surface-2)', 
            padding: '15px', 
            borderRadius: 'var(--radius-sm)' 
          }}>
            <div style={{ marginBottom: '10px' }}>
              <strong>Type:</strong> {selectedTable.type} | 
              <strong> Estimated Rows:</strong> {selectedTable.estimated_rows?.toLocaleString() || 'Unknown'} | 
              <strong> Columns:</strong> {selectedTable.columns.length}
            </div>
            
            <div>
              <strong>Columns:</strong>
              <div style={{ 
                maxHeight: '200px', 
                overflowY: 'auto', 
                marginTop: '10px',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)'
              }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'var(--surface-2)' }}>
                      <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>Name</th>
                      <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>Type</th>
                      <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>Nullable</th>
                      <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>Primary Key</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedTable.columns.map(column => (
                      <tr key={column.name}>
                        <td style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>
                          {column.name}
                        </td>
                        <td style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>
                          {column.data_type}
                        </td>
                        <td style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>
                          {column.is_nullable ? 'Yes' : 'No'}
                        </td>
                        <td style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>
                          {column.is_primary_key ? '✓' : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SchemaBrowser
