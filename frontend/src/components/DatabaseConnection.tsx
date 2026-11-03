import React, { useState } from 'react'

interface ConnectionParams {
  host: string
  port: number
  database: string
  user: string
  password: string
}

interface DatabaseConnectionProps {
  onConnectionSuccess: (result: any) => void
  onConnectionError: (error: string) => void
}

const DatabaseConnection: React.FC<DatabaseConnectionProps> = ({ 
  onConnectionSuccess, 
  onConnectionError 
}) => {
  const [connectionParams, setConnectionParams] = useState<ConnectionParams>({
    host: 'localhost',
    port: 5432,
    database: '',
    user: '',
    password: ''
  })
  const [isTesting, setIsTesting] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<string>('')

  const handleInputChange = (field: keyof ConnectionParams, value: string | number) => {
    setConnectionParams(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const testConnection = async () => {
    setIsTesting(true)
    setConnectionStatus('Testing connection...')

    try {
      const response = await fetch('/api/database/test-connection', {
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
        setConnectionStatus('Connection successful')
        onConnectionSuccess(result)
      } else {
        setConnectionStatus(`Connection failed: ${result.error}`)
        onConnectionError(result.error)
      }
    } catch (error) {
      setConnectionStatus(`Connection error: ${error instanceof Error ? error.message : 'Unknown error'}`)
      onConnectionError('Connection failed')
    } finally {
      setIsTesting(false)
    }
  }

  const getSchemas = async () => {
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
        setConnectionStatus(`Found ${result.schemas.length} schemas`)
        return result.schemas
      } else {
        setConnectionStatus(`Failed to get schemas: ${result.error}`)
        return []
      }
    } catch (error) {
      setConnectionStatus(`Schema error: ${error instanceof Error ? error.message : 'Unknown error'}`)
      return []
    }
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Database Connection</h3>
      
      <div style={{ 
        backgroundColor: 'var(--surface-2)', 
        padding: '20px', 
        borderRadius: 'var(--radius)',
        marginBottom: '20px'
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Host:
            </label>
            <input
              type="text"
              value={connectionParams.host}
              onChange={(e) => handleInputChange('host', e.target.value)}
              style={{ 
                width: '100%', 
                padding: '8px', 
                border: '1px solid var(--border)', 
                borderRadius: 'var(--radius-sm)' 
              }}
              placeholder="localhost"
            />
          </div>
          
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Port:
            </label>
            <input
              type="number"
              value={connectionParams.port}
              onChange={(e) => handleInputChange('port', parseInt(e.target.value))}
              style={{ 
                width: '100%', 
                padding: '8px', 
                border: '1px solid var(--border)', 
                borderRadius: 'var(--radius-sm)' 
              }}
              placeholder="5432"
            />
          </div>
          
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Database:
            </label>
            <input
              type="text"
              value={connectionParams.database}
              onChange={(e) => handleInputChange('database', e.target.value)}
              style={{ 
                width: '100%', 
                padding: '8px', 
                border: '1px solid var(--border)', 
                borderRadius: 'var(--radius-sm)' 
              }}
              placeholder="database_name"
            />
          </div>
          
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Username:
            </label>
            <input
              type="text"
              value={connectionParams.user}
              onChange={(e) => handleInputChange('user', e.target.value)}
              style={{ 
                width: '100%', 
                padding: '8px', 
                border: '1px solid var(--border)', 
                borderRadius: 'var(--radius-sm)' 
              }}
              placeholder="username"
            />
          </div>
          
          <div style={{ gridColumn: 'span 2' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Password:
            </label>
            <input
              type="password"
              value={connectionParams.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              style={{ 
                width: '100%', 
                padding: '8px', 
                border: '1px solid var(--border)', 
                borderRadius: 'var(--radius-sm)' 
              }}
              placeholder="password"
            />
          </div>
        </div>
        
        <div style={{ marginTop: '15px' }}>
          <button
            onClick={testConnection}
            disabled={isTesting}
            style={{ 
              padding: '10px 20px',
              backgroundColor: 'var(--primary)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: isTesting ? 'not-allowed' : 'pointer',
              opacity: isTesting ? 0.6 : 1
            }}
          >
            {isTesting ? 'Testing...' : 'Test Connection'}
          </button>
          
          <button
            onClick={getSchemas}
            style={{ 
              padding: '10px 20px',
              backgroundColor: 'var(--success)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              marginLeft: '10px'
            }}
          >
            Get Schemas
          </button>
        </div>
        
        {connectionStatus && (
          <div style={{ 
            marginTop: '15px', 
            padding: '10px', 
            backgroundColor: /successful|Found/.test(connectionStatus) ? 'var(--success-soft)' : 'var(--danger-soft)',
            color: /successful|Found/.test(connectionStatus) ? 'var(--success)' : 'var(--danger)',
            borderRadius: 'var(--radius-sm)',
            border: `1px solid ${/successful|Found/.test(connectionStatus) ? 'var(--success-soft)' : 'var(--danger-soft)'}`
          }}>
            {connectionStatus}
          </div>
        )}
      </div>
    </div>
  )
}

export default DatabaseConnection
