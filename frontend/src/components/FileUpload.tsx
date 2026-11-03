import React, { useState, useRef } from 'react'

interface FileUploadProps {
  onUploadComplete: (result: any) => void
  onUploadError: (error: string) => void
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadComplete, onUploadError }) => {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    
    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  const handleFileUpload = async (file: File) => {
    // Validate file type
    const allowedTypes = ['.csv', '.xlsx', '.xls']
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
    
    if (!allowedTypes.includes(fileExtension)) {
      onUploadError('Please select a CSV, XLSX, or XLS file')
      return
    }

    // Validate file size (50MB)
    const maxSize = 50 * 1024 * 1024
    if (file.size > maxSize) {
      onUploadError('File size must be less than 50MB')
      return
    }

    setIsUploading(true)
    setUploadProgress(0)

    try {
      const formData = new FormData()
      formData.append('file', file)

      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return 90
          }
          return prev + 10
        })
      }, 100)

      const response = await fetch('/api/upload/file', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })

      clearInterval(progressInterval)
      setUploadProgress(100)

      if (response.ok) {
        const result = await response.json()
        onUploadComplete(result)
      } else {
        const errorData = await response.json()
        onUploadError(errorData.detail || 'Upload failed')
      }
    } catch (error) {
      console.error('Upload error:', error)
      onUploadError('Upload failed: ' + (error instanceof Error ? error.message : 'Network error - check if backend is running'))
    } finally {
      setIsUploading(false)
      setUploadProgress(0)
    }
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Upload File</h3>
      
      <div
        className={`dropzone ${isDragging ? 'dragging' : ''}`}
        style={{
          borderRadius: 'var(--radius)',
          padding: '40px',
          textAlign: 'center',
          backgroundColor: isDragging ? 'var(--surface-2)' : 'var(--surface-2)',
          cursor: 'pointer',
          transition: 'all 0.3s ease'
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
        
        {isUploading ? (
          <div>
            <div style={{ fontSize: '18px', marginBottom: '10px' }}>Uploading...</div>
            <div style={{ 
              width: '100%', 
              height: '20px', 
              backgroundColor: 'var(--border)', 
              borderRadius: 'var(--radius-sm)',
              overflow: 'hidden'
            }}>
              <div style={{
                width: `${uploadProgress}%`,
                height: '100%',
                backgroundColor: 'var(--primary)',
                transition: 'width 0.3s ease'
              }} />
            </div>
            <div style={{ marginTop: '10px', fontSize: '14px' }}>{uploadProgress}%</div>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: '48px', marginBottom: '10px' }}>⬆</div>
            <div style={{ fontSize: '18px', marginBottom: '10px' }}>
              {isDragging ? 'Drop file here' : 'Click to select or drag file here'}
            </div>
            <div style={{ fontSize: '14px', color: 'var(--text-2)' }}>
              Supported formats: CSV, XLSX, XLS (max 50MB)
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default FileUpload
