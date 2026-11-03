"""Import diagnostics generation for file uploads."""
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.shared.logger import get_logger

logger = get_logger(__name__)


class ImportDiagnostics:
    """Generates import diagnostics for file uploads."""
    
    def generate_diagnostics(self, parse_result: Dict[str, Any], file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate import diagnostics."""
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'file_info': file_info,
            'parse_status': 'success' if parse_result.get('success') else 'failed',
            'issues': [],
            'warnings': [],
            'summary': {},
            'recommendations': []
        }
        
        if not parse_result.get('success'):
            diagnostics['issues'].append({
                'type': 'parse_error',
                'severity': 'error',
                'message': parse_result.get('error', 'Unknown parsing error'),
                'suggestion': 'Check file format and try again'
            })
            return diagnostics
        
        # Generate diagnostics based on file type
        if parse_result.get('file_type') == 'csv':
            self._generate_csv_diagnostics(parse_result, diagnostics)
        elif parse_result.get('file_type') in ['xlsx', 'xls']:
            self._generate_excel_diagnostics(parse_result, diagnostics)
        
        # Generate summary
        diagnostics['summary'] = self._generate_summary(parse_result)
        
        # Generate recommendations
        diagnostics['recommendations'] = self._generate_recommendations(parse_result, diagnostics)
        
        logger.info("Import diagnostics generated", 
                   issues=len(diagnostics['issues']),
                   warnings=len(diagnostics['warnings']))
        
        return diagnostics
    
    def _generate_csv_diagnostics(self, parse_result: Dict[str, Any], diagnostics: Dict[str, Any]):
        """Generate CSV-specific diagnostics."""
        # Check for encoding issues
        encoding = parse_result.get('encoding', 'unknown')
        if encoding != 'utf-8':
            diagnostics['warnings'].append({
                'type': 'encoding',
                'severity': 'warning',
                'message': f'File encoded as {encoding}, not UTF-8',
                'suggestion': 'Consider converting to UTF-8 for better compatibility'
            })
        
        # Check for delimiter issues
        delimiter = parse_result.get('delimiter', ',')
        if delimiter != ',':
            diagnostics['warnings'].append({
                'type': 'delimiter',
                'severity': 'warning',
                'message': f'File uses "{delimiter}" as delimiter, not comma',
                'suggestion': 'Verify data structure is correct'
            })
        
        # Check for empty rows/columns
        column_stats = parse_result.get('column_stats', [])
        for stat in column_stats:
            if stat['empty_count'] > stat['non_empty_count'] * 0.5:
                diagnostics['warnings'].append({
                    'type': 'empty_column',
                    'severity': 'warning',
                    'message': f'Column {stat["column_index"]} is mostly empty ({stat["empty_count"]} empty vs {stat["non_empty_count"]} non-empty)',
                    'suggestion': 'Consider removing or reviewing this column'
                })
        
        # Check for duplicate headers
        headers = parse_result.get('headers', [])
        if len(headers) != len(set(headers)):
            diagnostics['issues'].append({
                'type': 'duplicate_headers',
                'severity': 'error',
                'message': 'Duplicate column headers detected',
                'suggestion': 'Headers have been automatically renamed, but review original file'
            })
    
    def _generate_excel_diagnostics(self, parse_result: Dict[str, Any], diagnostics: Dict[str, Any]):
        """Generate Excel-specific diagnostics."""
        # Check for formula issues
        formula_issues = parse_result.get('formula_issues', [])
        for issue in formula_issues:
            diagnostics['issues'].append({
                'type': 'formula_issue',
                'severity': 'warning',
                'message': f'Formula issue in cell {issue.get("cell", "unknown")}: {issue.get("description", "Unknown issue")}',
                'suggestion': 'Review formulas in original file'
            })
        
        # Check for multiple sheets
        available_sheets = parse_result.get('available_sheets', [])
        if len(available_sheets) > 1:
            diagnostics['warnings'].append({
                'type': 'multiple_sheets',
                'severity': 'info',
                'message': f'File contains {len(available_sheets)} sheets: {", ".join(available_sheets)}',
                'suggestion': f'Currently using sheet: {parse_result.get("sheet_name", "unknown")}'
            })
        
        # Check for empty rows/columns (same as CSV)
        column_stats = parse_result.get('column_stats', [])
        for stat in column_stats:
            if stat['empty_count'] > stat['non_empty_count'] * 0.5:
                diagnostics['warnings'].append({
                    'type': 'empty_column',
                    'severity': 'warning',
                    'message': f'Column {stat["column_index"]} is mostly empty ({stat["empty_count"]} empty vs {stat["non_empty_count"]} non-empty)',
                    'suggestion': 'Consider removing or reviewing this column'
                })
    
    def _generate_summary(self, parse_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate import summary."""
        total_rows = parse_result.get('total_rows', 0)
        preview_rows = len(parse_result.get('preview_rows', []))
        headers = parse_result.get('headers', [])
        
        return {
            'total_rows': total_rows,
            'preview_rows': preview_rows,
            'total_columns': len(headers),
            'file_type': parse_result.get('file_type', 'unknown'),
            'encoding': parse_result.get('encoding'),
            'delimiter': parse_result.get('delimiter'),
            'sheet_name': parse_result.get('sheet_name')
        }
    
    def _generate_recommendations(self, parse_result: Dict[str, Any], diagnostics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on diagnostics."""
        recommendations = []
        
        # Check for data quality issues
        column_stats = parse_result.get('column_stats', [])
        empty_columns = [s for s in column_stats if s['empty_count'] > s['non_empty_count'] * 0.8]
        
        if empty_columns:
            recommendations.append(f"Consider removing {len(empty_columns)} mostly empty columns")
        
        # Check for encoding issues
        if parse_result.get('encoding') and parse_result['encoding'] != 'utf-8':
            recommendations.append("Convert file to UTF-8 encoding for better compatibility")
        
        # Check for delimiter issues
        if parse_result.get('delimiter') and parse_result['delimiter'] != ',':
            recommendations.append("Verify delimiter detection is correct")
        
        # Check for formula issues
        if parse_result.get('formula_issues'):
            recommendations.append("Review and resolve formula issues in original file")
        
        # Check for multiple sheets
        if len(parse_result.get('available_sheets', [])) > 1:
            recommendations.append("Confirm correct sheet is selected for import")
        
        # General recommendations
        if parse_result.get('total_rows', 0) > 10000:
            recommendations.append("Large file detected - consider filtering data before import")
        
        if not recommendations:
            recommendations.append("File appears to be in good condition for import")
        
        return recommendations
    
    def generate_error_diagnostics(self, error_message: str, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate diagnostics for failed imports."""
        return {
            'timestamp': datetime.now().isoformat(),
            'file_info': file_info,
            'parse_status': 'failed',
            'issues': [{
                'type': 'import_error',
                'severity': 'error',
                'message': error_message,
                'suggestion': 'Check file format and try again'
            }],
            'warnings': [],
            'summary': {
                'total_rows': 0,
                'preview_rows': 0,
                'total_columns': 0,
                'file_type': 'unknown'
            },
            'recommendations': ['Fix the error and try uploading again']
        }


# Global import diagnostics instance
import_diagnostics = ImportDiagnostics()
