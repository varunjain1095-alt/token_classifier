"""File validation and format checking."""
import os
from typing import Dict, Any, Optional

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

from src.shared.logger import get_logger

logger = get_logger(__name__)


class FileValidator:
    """Validates file format and content."""
    
    def __init__(self):
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.supported_mime_types = {
            'text/csv': 'csv',
            'application/vnd.ms-excel': 'xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
            'application/vnd.ms-excel.sheet.macroEnabled.12': 'xlsm',
            'application/vnd.ms-excel.sheet.binary.macroEnabled.12': 'xlsb'
        }
    
    def validate_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Validate uploaded file."""
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return {'valid': False, 'error': 'File not found'}
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                return {'valid': False, 'error': f'File too large: {file_size} bytes'}
            
            # Check file extension
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension not in ['.csv', '.xlsx', '.xls']:
                return {'valid': False, 'error': f'Unsupported extension: {file_extension}'}
            
            # Detect MIME type
            mime_type = self._detect_mime_type(file_path)
            
            # Validate MIME type matches extension
            expected_mime = self._get_expected_mime_type(file_extension)
            if mime_type and expected_mime and mime_type != expected_mime:
                logger.warning("MIME type mismatch", 
                             expected=expected_mime, 
                             detected=mime_type,
                             filename=filename)
                # Don't fail, but log the mismatch
            
            # Check for malicious content
            security_check = self._security_check(file_path, file_extension)
            if not security_check['safe']:
                return {'valid': False, 'error': security_check['error']}
            
            return {
                'valid': True,
                'file_size': file_size,
                'file_extension': file_extension,
                'mime_type': mime_type,
                'detected_type': self._detect_file_type(file_path, file_extension)
            }
            
        except Exception as e:
            logger.error("File validation failed", error=str(e), filename=filename)
            return {'valid': False, 'error': f'Validation error: {str(e)}'}
    
    def _detect_mime_type(self, file_path: str) -> Optional[str]:
        """Detect file MIME type."""
        try:
            # Try python-magic first if available
            if MAGIC_AVAILABLE:
                try:
                    mime = magic.Magic(mime=True)
                    return mime.from_file(file_path)
                except Exception:
                    pass
            
            # Fallback to file signature detection
            return self._detect_by_signature(file_path)
        except Exception as e:
            logger.error("MIME type detection failed", error=str(e))
            return None
    
    def _detect_by_signature(self, file_path: str) -> Optional[str]:
        """Detect file type by signature."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(512)
            
            # Check for Excel file signatures
            if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
                return 'application/vnd.ms-excel'  # XLS
            
            if header.startswith(b'PK\x03\x04'):
                return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # XLSX
            
            # Check for CSV (text-based)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    sample = f.read(1024)
                    if ',' in sample or '\t' in sample or ';' in sample:
                        return 'text/csv'
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.error("Signature detection failed", error=str(e))
            return None
    
    def _get_expected_mime_type(self, file_extension: str) -> Optional[str]:
        """Get expected MIME type for file extension."""
        extension_map = {
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel'
        }
        return extension_map.get(file_extension)
    
    def _security_check(self, file_path: str, file_extension: str) -> Dict[str, Any]:
        """Perform security checks on file."""
        try:
            # Check file size again
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return {'safe': False, 'error': 'File is empty'}
            
            # Check for embedded macros or scripts (basic check)
            if file_extension in ['.xlsx', '.xls']:
                with open(file_path, 'rb') as f:
                    content = f.read(1024)  # Check first 1KB
                    
                    # Look for suspicious patterns
                    suspicious_patterns = [
                        b'vbaProject',  # VBA macros
                        b'Macros',
                        b'Script',
                        b'JavaScript'
                    ]
                    
                    for pattern in suspicious_patterns:
                        if pattern in content:
                            return {'safe': False, 'error': 'File contains potentially unsafe content'}
            
            # For CSV files, check for formula injection attempts
            if file_extension == '.csv':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    sample = f.read(1024)
                    
                    # Check for formula injection patterns
                    dangerous_patterns = ['=', '+', '-', '@']
                    lines = sample.split('\n')[:5]  # Check first 5 lines
                    
                    for line in lines:
                        for cell in line.split(','):
                            cell = cell.strip()
                            if cell and cell[0] in dangerous_patterns:
                                return {'safe': False, 'error': 'File contains formula injection attempts'}
            
            return {'safe': True}
            
        except Exception as e:
            logger.error("Security check failed", error=str(e))
            return {'safe': False, 'error': f'Security check error: {str(e)}'}
    
    def _detect_file_type(self, file_path: str, file_extension: str) -> str:
        """Detect actual file type."""
        try:
            # Use signature detection as fallback
            signature_type = self._detect_by_signature(file_path)
            
            if signature_type:
                if 'excel' in signature_type or 'spreadsheet' in signature_type:
                    return 'excel'
                elif 'csv' in signature_type or 'text' in signature_type:
                    return 'csv'
            
            # Fallback to extension
            if file_extension == '.csv':
                return 'csv'
            elif file_extension in ['.xlsx', '.xls']:
                return 'excel'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error("File type detection failed", error=str(e))
            return 'unknown'


# Global file validator instance
file_validator = FileValidator()
