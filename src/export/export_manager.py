"""Export and reporting system for classification results."""
import uuid
import json
import csv
import io
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class ExportFormat(Enum):
    """Export format."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"


class ExportType(Enum):
    """Export type."""
    RESULTS_ONLY = "results_only"
    FULL_REPORT = "full_report"
    SUMMARY = "summary"
    RAW_DATA = "raw_data"


class ExportManager:
    """Manages export and reporting functionality."""
    
    def __init__(self):
        self.exports = {}  # In-memory storage for now
        self.supported_formats = ['csv', 'json', 'excel', 'pdf']
        self.supported_types = ['results_only', 'full_report', 'summary', 'raw_data']
    
    def create_export(self, user_id: str, execution_id: str, 
                     export_type: str, export_format: str,
                     filters: Optional[Dict[str, Any]] = None,
                     include_metadata: bool = True) -> Dict[str, Any]:
        """Create a new export."""
        try:
            export_id = str(uuid.uuid4())
            
            # Validate inputs
            if export_format not in self.supported_formats:
                return {
                    'success': False,
                    'error': f'Unsupported format: {export_format}'
                }
            
            if export_type not in self.supported_types:
                return {
                    'success': False,
                    'error': f'Unsupported type: {export_type}'
                }
            
            # Create export record
            export = {
                'id': export_id,
                'user_id': user_id,
                'execution_id': execution_id,
                'export_type': export_type,
                'export_format': export_format,
                'filters': filters or {},
                'include_metadata': include_metadata,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'processing',
                'file_path': None,
                'file_size': 0,
                'record_count': 0
            }
            
            self.exports[export_id] = export
            
            logger.info("Export created", 
                       export_id=export_id,
                       execution_id=execution_id,
                       export_type=export_type,
                       export_format=export_format)
            
            return {
                'success': True,
                'export_id': export_id,
                'export': export
            }
            
        except Exception as e:
            logger.error("Failed to create export", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_export_file(self, export_id: str, execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the actual export file."""
        try:
            export = self.exports.get(export_id)
            if not export:
                return {
                    'success': False,
                    'error': 'Export not found'
                }
            
            export['status'] = 'generating'
            
            # Extract data based on export type
            export_data = self._extract_export_data(export, execution_data)
            
            # Generate file based on format
            file_content = self._generate_file_content(export, export_data)
            
            # Update export record
            export['status'] = 'completed'
            export['completed_at'] = datetime.utcnow().isoformat()
            export['record_count'] = len(export_data.get('records', []))
            export['file_size'] = len(file_content.encode('utf-8'))
            
            logger.info("Export file generated", 
                       export_id=export_id,
                       file_size=export['file_size'],
                       record_count=export['record_count'])
            
            return {
                'success': True,
                'export_id': export_id,
                'file_content': file_content,
                'file_size': export['file_size'],
                'record_count': export['record_count'],
                'filename': self._generate_filename(export)
            }
            
        except Exception as e:
            export['status'] = 'failed'
            export['error'] = str(e)
            logger.error("Failed to generate export file", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_export_data(self, export: Dict[str, Any], execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data based on export type."""
        export_type = export['export_type']
        filters = export['filters']
        
        if export_type == ExportType.RESULTS_ONLY.value:
            # Just the classification results
            records = []
            for result in execution_data.get('results', []):
                record = {
                    'record_id': result.get('record_id'),
                    'classification': result.get('classification'),
                    'confidence': result.get('confidence'),
                    'timestamp': result.get('timestamp')
                }
                records.append(record)
            
            return {
                'records': records,
                'metadata': {
                    'total_records': len(records),
                    'execution_id': export['execution_id'],
                    'export_type': export_type,
                    'exported_at': datetime.utcnow().isoformat()
                }
            }
        
        elif export_type == ExportType.FULL_REPORT.value:
            # Complete report with all data
            records = []
            for result in execution_data.get('results', []):
                record = {
                    'record_id': result.get('record_id'),
                    'original_text': result.get('record', {}).get('review_text', ''),
                    'classification': result.get('classification'),
                    'confidence': result.get('confidence'),
                    'reasoning': result.get('reasoning', ''),
                    'timestamp': result.get('timestamp'),
                    'token_usage': result.get('token_usage', {})
                }
                records.append(record)
            
            return {
                'records': records,
                'metadata': {
                    'total_records': len(records),
                    'execution_id': export['execution_id'],
                    'export_type': export_type,
                    'execution_summary': execution_data.get('summary', {}),
                    'exported_at': datetime.utcnow().isoformat()
                }
            }
        
        elif export_type == ExportType.SUMMARY.value:
            # Summary statistics only
            summary = execution_data.get('summary', {})
            analysis = execution_data.get('final_analysis', {})
            
            return {
                'records': [{
                    'metric': 'Total Records',
                    'value': summary.get('total_processed', 0)
                }, {
                    'metric': 'Successful',
                    'value': summary.get('successful', 0)
                }, {
                    'metric': 'Failed',
                    'value': summary.get('failed', 0)
                }, {
                    'metric': 'Success Rate',
                    'value': f"{summary.get('success_rate', 0):.1f}%"
                }, {
                    'metric': 'Actual Cost',
                    'value': f"${summary.get('actual_cost', 0):.6f}"
                }, {
                    'metric': 'Total Tokens',
                    'value': summary.get('token_usage', {}).get('total_tokens', 0)
                }],
                'metadata': {
                    'export_type': export_type,
                    'execution_id': export['execution_id'],
                    'exported_at': datetime.utcnow().isoformat()
                }
            }
        
        else:  # RAW_DATA
            # All raw execution data
            return {
                'records': execution_data.get('results', []),
                'errors': execution_data.get('errors', []),
                'metadata': {
                    'export_type': export_type,
                    'execution_id': export['execution_id'],
                    'execution_summary': execution_data.get('summary', {}),
                    'exported_at': datetime.utcnow().isoformat()
                }
            }
    
    def _generate_file_content(self, export: Dict[str, Any], export_data: Dict[str, Any]) -> str:
        """Generate file content based on format."""
        export_format = export['export_format']
        
        if export_format == ExportFormat.CSV.value:
            return self._generate_csv_content(export_data)
        
        elif export_format == ExportFormat.JSON.value:
            return self._generate_json_content(export_data)
        
        elif export_format == ExportFormat.EXCEL.value:
            # For now, return CSV format (Excel support would need openpyxl)
            return self._generate_csv_content(export_data)
        
        elif export_format == ExportFormat.PDF.value:
            # For now, return JSON format (PDF support would need reportlab)
            return self._generate_json_content(export_data)
        
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
    
    def _generate_csv_content(self, export_data: Dict[str, Any]) -> str:
        """Generate CSV content."""
        records = export_data.get('records', [])
        if not records:
            return "No data to export"
        
        # Get all unique keys for headers
        all_keys = set()
        for record in records:
            all_keys.update(record.keys())
        
        headers = sorted(list(all_keys))
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        for record in records:
            # Flatten nested objects
            flattened = {}
            for key, value in record.items():
                if isinstance(value, dict):
                    flattened[key] = json.dumps(value)
                else:
                    flattened[key] = value
            writer.writerow(flattened)
        
        return output.getvalue()
    
    def _generate_json_content(self, export_data: Dict[str, Any]) -> str:
        """Generate JSON content."""
        return json.dumps(export_data, indent=2, default=str)
    
    def _generate_filename(self, export: Dict[str, Any]) -> str:
        """Generate filename for export."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f"classification_export_{export['export_type']}_{export['export_format']}_{timestamp}.{export['export_format']}"
    
    def get_export(self, export_id: str) -> Optional[Dict[str, Any]]:
        """Get export by ID."""
        return self.exports.get(export_id)
    
    def get_user_exports(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all exports for user."""
        user_exports = []
        for export in self.exports.values():
            if export['user_id'] == user_id:
                user_exports.append(export)
        
        # Sort by creation date (newest first)
        user_exports.sort(key=lambda x: x['created_at'], reverse=True)
        return user_exports
    
    def delete_export(self, export_id: str) -> Dict[str, Any]:
        """Delete export."""
        if export_id in self.exports:
            del self.exports[export_id]
            logger.info("Export deleted", export_id=export_id)
            return {'success': True}
        else:
            return {'success': False, 'error': 'Export not found'}
    
    def get_export_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get export statistics for user."""
        user_exports = self.get_user_exports(user_id)
        
        total_exports = len(user_exports)
        completed_exports = len([e for e in user_exports if e['status'] == 'completed'])
        failed_exports = len([e for e in user_exports if e['status'] == 'failed'])
        
        format_counts = {}
        type_counts = {}
        
        for export in user_exports:
            format_counts[export['export_format']] = format_counts.get(export['export_format'], 0) + 1
            type_counts[export['export_type']] = type_counts.get(export['export_type'], 0) + 1
        
        return {
            'total_exports': total_exports,
            'completed_exports': completed_exports,
            'failed_exports': failed_exports,
            'success_rate': (completed_exports / max(total_exports, 1)) * 100,
            'format_distribution': format_counts,
            'type_distribution': type_counts
        }


# Global export manager instance
export_manager = ExportManager()
