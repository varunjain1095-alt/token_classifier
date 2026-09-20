"""File upload handling with validation."""
import os
import uuid
from typing import Optional, Dict, Any, BinaryIO
from fastapi import UploadFile, HTTPException
from werkzeug.utils import secure_filename

from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.identity.ownership import ownership_manager
from src.identity.retention_metadata import retention_metadata, DataType

logger = get_logger(__name__)


class FileUploadHandler:
    """Handles file uploads with validation and security."""
    
    def __init__(self):
        self.settings = get_settings()
        self.upload_folder = self.settings.upload_folder
        self.max_upload_size = self.settings.max_upload_size
        self._ensure_upload_folder()
    
    def _ensure_upload_folder(self):
        """Ensure upload folder exists."""
        os.makedirs(self.upload_folder, exist_ok=True)
    
    async def handle_upload(self, file: UploadFile, session_id: str) -> Dict[str, Any]:
        """Handle file upload with validation."""
        try:
            # Validate file
            validation_result = await self._validate_file(file)
            if not validation_result['valid']:
                raise HTTPException(status_code=400, detail=validation_result['error'])
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            original_filename = file.filename or "unknown"
            safe_filename = secure_filename(original_filename)
            file_extension = self._get_file_extension(safe_filename)
            
            # Create filename with ID to prevent collisions
            filename = f"{file_id}_{safe_filename}"
            file_path = os.path.join(self.upload_folder, filename)
            
            # Save file
            file_content = await file.read()
            file_size = len(file_content)
            
            if file_size > self.max_upload_size:
                raise HTTPException(status_code=413, detail="File too large")
            
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Create source record
            source_data = {
                'id': file_id,
                'type': 'file',
                'display_name': original_filename,
                'format_adapter': self._get_format_adapter(file_extension),
                'file_reference': file_path,
                'file_size': file_size,
                'content_type': file.content_type
            }
            
            # Set ownership
            ownership_manager.validate_entity_creation(session_id, source_data)
            
            logger.info("File uploaded successfully", 
                       file_id=file_id[:8], 
                       filename=original_filename,
                       size=file_size)
            
            return {
                'file_id': file_id,
                'filename': original_filename,
                'file_path': file_path,
                'file_size': file_size,
                'file_extension': file_extension,
                'source_data': source_data
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("File upload failed", error=str(e))
            raise HTTPException(status_code=500, detail="File upload failed")
    
    async def _validate_file(self, file: UploadFile) -> Dict[str, Any]:
        """Validate uploaded file."""
        if not file.filename:
            return {'valid': False, 'error': 'No filename provided'}
        
        # Check file extension
        file_extension = self._get_file_extension(file.filename)
        if file_extension not in ['.csv', '.xlsx', '.xls']:
            return {'valid': False, 'error': f'Unsupported file format: {file_extension}'}
        
        # Check file size (if available)
        if hasattr(file, 'size') and file.size and file.size > self.max_upload_size:
            return {'valid': False, 'error': 'File too large'}
        
        # Check for dangerous file types
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.sh', '.php', '.js']
        if any(file.filename.lower().endswith(ext) for ext in dangerous_extensions):
            return {'valid': False, 'error': 'File type not allowed'}
        
        return {'valid': True}
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension."""
        return os.path.splitext(filename)[1].lower()
    
    def _get_format_adapter(self, file_extension: str) -> str:
        """Get format adapter name for file type."""
        adapters = {
            '.csv': 'csv_parser',
            '.xlsx': 'xlsx_parser',
            '.xls': 'xls_parser'
        }
        return adapters.get(file_extension, 'unknown')
    
    def cleanup_file(self, file_path: str) -> bool:
        """Clean up uploaded file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("File cleaned up", file_path=file_path)
                return True
            return False
        except Exception as e:
            logger.error("Failed to cleanup file", file_path=file_path, error=str(e))
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about uploaded file."""
        if not os.path.exists(file_path):
            return None
        
        try:
            stat = os.stat(file_path)
            return {
                'file_path': file_path,
                'file_size': stat.st_size,
                'created_time': stat.st_ctime,
                'modified_time': stat.st_mtime
            }
        except Exception as e:
            logger.error("Failed to get file info", file_path=file_path, error=str(e))
            return None


# Global file upload handler instance
file_upload_handler = FileUploadHandler()
