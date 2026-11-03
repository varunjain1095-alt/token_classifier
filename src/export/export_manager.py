"""Export and reporting system for classification results."""
import uuid
import json
import csv
import io
from pathlib import Path
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
        self.exports = {}  # Hot in-memory view; export metadata + files on disk
        self.storage_dir = Path('tmp/exports')
        self.supported_formats = ['csv', 'json', 'xlsx', 'excel', 'pdf']
        self.supported_types = ['results_only', 'full_report', 'summary', 'raw_data']

    def _persist(self, export: Dict[str, Any]) -> None:
        """Write export metadata to disk so history survives a restart."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            (self.storage_dir / f"{export['id']}.meta.json").write_text(
                json.dumps(export, default=str), encoding='utf-8')
        except Exception as e:
            logger.warning("Failed to persist export",
                           export_id=export.get('id'), error=str(e))

    def _load(self, export_id: str) -> Optional[Dict[str, Any]]:
        """Return an export from memory, or restore its metadata from disk."""
        export = self.exports.get(export_id)
        if export:
            return export
        path = self.storage_dir / f"{export_id}.meta.json"
        if not path.exists():
            return None
        try:
            export = json.loads(path.read_text(encoding='utf-8'))
            self.exports[export_id] = export
            return export
        except Exception as e:
            logger.warning("Failed to load export checkpoint",
                           export_id=export_id, error=str(e))
            return None
    
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
            self._persist(export)

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

            # Generate file based on format (binary for xlsx, text otherwise)
            file_bytes = None
            file_content = None
            if self._is_excel(export['export_format']):
                file_bytes = self._generate_xlsx_content(export_data)
            else:
                file_content = self._generate_file_content(export, export_data)

            # Persist the generated file so downloads survive restarts
            filename = self._generate_filename(export)
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            path = self.storage_dir / filename
            if file_bytes is not None:
                path.write_bytes(file_bytes)
                file_size = len(file_bytes)
            else:
                path.write_text(file_content, encoding='utf-8')
                file_size = len(file_content.encode('utf-8'))

            # Update export record
            export['status'] = 'completed'
            export['completed_at'] = datetime.utcnow().isoformat()
            export['record_count'] = len(export_data.get('records', []))
            export['file_size'] = file_size
            export['file_path'] = str(path)
            self._persist(export)

            logger.info("Export file generated",
                       export_id=export_id,
                       file_size=export['file_size'],
                       record_count=export['record_count'])

            return {
                'success': True,
                'export_id': export_id,
                'file_content': file_content,
                'file_bytes': file_bytes,
                'file_size': export['file_size'],
                'record_count': export['record_count'],
                'filename': filename
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
            records = [self._flatten_record(r, include_source=False)
                       for r in execution_data.get('results', [])]
            
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
            # Complete report: review text + one column per classification field
            records = [self._flatten_record(r, include_source=True)
                       for r in execution_data.get('results', [])]
            
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
    
    def _flatten_record(self, result: Dict[str, Any],
                        include_source: bool = True) -> Dict[str, Any]:
        """Flatten one execution result into an export row: review text +
        one column per classification field (no nested JSON blobs)."""
        source = result.get('record') or {}
        row = {
            'record_id': result.get('record_id'),
            'review_text': (source.get('original_review_text')
                            or source.get('review_text')
                            or source.get('text') or ''),
        }
        classification = result.get('classification')
        if isinstance(classification, dict):
            for key, value in classification.items():
                row[key] = (', '.join(str(v) for v in value)
                            if isinstance(value, list) else value)
        elif classification is not None:
            row['classification'] = classification
        if result.get('confidence') is not None and 'confidence' not in row:
            row['confidence'] = result['confidence']
        if result.get('reasoning') and 'reasoning' not in row:
            row['reasoning'] = result['reasoning']
        row['timestamp'] = result.get('timestamp')
        if include_source:
            for key, value in (source.get('mapped_metadata') or {}).items():
                if key not in row:
                    row[key] = value
        return row

    def _is_excel(self, export_format: str) -> bool:
        return export_format in (ExportFormat.EXCEL.value, 'xlsx')

    def _extension(self, export_format: str) -> str:
        return 'xlsx' if self._is_excel(export_format) else export_format

    def _generate_file_content(self, export: Dict[str, Any], export_data: Dict[str, Any]) -> str:
        """Generate file content based on format."""
        export_format = export['export_format']

        if export_format == ExportFormat.CSV.value:
            return self._generate_csv_content(export_data)

        elif export_format == ExportFormat.JSON.value or \
                export_format == ExportFormat.PDF.value:
            # PDF support would need reportlab; JSON is the fallback
            return self._generate_json_content(export_data)

        else:
            raise ValueError(f"Unsupported export format: {export_format}")

    def _generate_xlsx_content(self, export_data: Dict[str, Any]) -> bytes:
        """Generate a real Excel workbook from the flattened records."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = 'Classifications'

        records = export_data.get('records', [])
        headers: List[str] = []
        for record in records:
            for key in record.keys():
                if key not in headers:
                    headers.append(key)
        if headers:
            ws.append(headers)
            for record in records:
                ws.append([
                    json.dumps(v, default=str)
                    if isinstance(v, (dict, list)) else v
                    for v in (record.get(k) for k in headers)
                ])
        # Reasonable column widths so the file opens readable
        for i, header in enumerate(headers, start=1):
            max_len = max([len(str(header))] + [
                min(len(str(r.get(header, '') or '')), 80) for r in records])
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter] \
                .width = min(max_len + 2, 82)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    
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
        ext = self._extension(export['export_format'])
        return f"classification_export_{export['export_type']}_{ext}_{timestamp}.{ext}"

    def get_export(self, export_id: str) -> Optional[Dict[str, Any]]:
        """Get export by ID."""
        return self._load(export_id)

    def get_user_exports(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all exports for user."""
        # Restore export metadata written to disk by earlier runs
        if self.storage_dir.exists():
            for path in self.storage_dir.glob('*.meta.json'):
                key = path.name[:-len('.meta.json')]
                if key not in self.exports:
                    self._load(key)

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
