"""Excel file parsing for XLSX and XLS files."""
import pandas as pd
import openpyxl
import xlrd
from typing import List, Dict, Any, Optional, Tuple
import io

from src.shared.logger import get_logger

logger = get_logger(__name__)


class ExcelParser:
    """Parses Excel files (XLSX and XLS) with sheet selection."""
    
    def __init__(self):
        pass
    
    def get_sheet_names(self, file_content: bytes, file_extension: str) -> Dict[str, Any]:
        """Get available sheet names from Excel file."""
        try:
            if file_extension == '.xlsx':
                return self._get_xlsx_sheet_names(file_content)
            elif file_extension == '.xls':
                return self._get_xls_sheet_names(file_content)
            else:
                raise ValueError(f"Unsupported Excel format: {file_extension}")
                
        except Exception as e:
            logger.error("Failed to get sheet names", error=str(e), file_extension=file_extension)
            return {
                'success': False,
                'error': str(e),
                'file_type': 'excel'
            }
    
    def _get_xlsx_sheet_names(self, file_content: bytes) -> Dict[str, Any]:
        """Get sheet names from XLSX file."""
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True)
            sheet_names = workbook.sheetnames
            workbook.close()
            
            return {
                'success': True,
                'sheet_names': sheet_names,
                'file_type': 'xlsx'
            }
        except Exception as e:
            raise ValueError(f"Failed to read XLSX file: {str(e)}")
    
    def _get_xls_sheet_names(self, file_content: bytes) -> Dict[str, Any]:
        """Get sheet names from XLS file."""
        try:
            workbook = xlrd.open_workbook(file_contents=file_content)
            sheet_names = workbook.sheet_names()
            
            return {
                'success': True,
                'sheet_names': sheet_names,
                'file_type': 'xls'
            }
        except Exception as e:
            raise ValueError(f"Failed to read XLS file: {str(e)}")
    
    def parse_file(self, file_content: bytes, file_extension: str, 
                   sheet_name: Optional[str] = None, max_rows: int = 100) -> Dict[str, Any]:
        """Parse Excel file and return preview data."""
        try:
            if file_extension == '.xlsx':
                return self._parse_xlsx(file_content, sheet_name, max_rows)
            elif file_extension == '.xls':
                return self._parse_xls(file_content, sheet_name, max_rows)
            else:
                raise ValueError(f"Unsupported Excel format: {file_extension}")
                
        except Exception as e:
            logger.error("Excel parsing failed", error=str(e), file_extension=file_extension)
            return {
                'success': False,
                'error': str(e),
                'file_type': 'excel'
            }
    
    def _parse_xlsx(self, file_content: bytes, sheet_name: Optional[str], max_rows: int) -> Dict[str, Any]:
        """Parse XLSX file."""
        try:
            # Read with pandas for better handling
            excel_file = pd.ExcelFile(io.BytesIO(file_content))
            
            # Use specified sheet or first sheet
            sheet = sheet_name or excel_file.sheet_names[0]
            
            if sheet not in excel_file.sheet_names:
                raise ValueError(f"Sheet '{sheet}' not found in workbook")
            
            # Read data
            df = pd.read_excel(excel_file, sheet_name=sheet, nrows=max_rows)
            
            # Convert to list of lists
            headers = [str(col) for col in df.columns]
            data_rows = df.values.tolist()
            
            # Handle duplicate headers
            headers = self._deduplicate_headers(headers)
            
            # Generate column statistics
            column_stats = self._generate_column_stats(data_rows, len(headers))
            
            # Check for formula issues
            formula_issues = self._check_formula_issues(file_content, sheet)
            
            result = {
                'success': True,
                'sheet_name': sheet,
                'available_sheets': excel_file.sheet_names,
                'headers': headers,
                'total_rows': len(data_rows),
                'preview_rows': data_rows,
                'column_stats': column_stats,
                'formula_issues': formula_issues,
                'file_type': 'xlsx'
            }
            
            logger.info("XLSX parsed successfully", 
                       sheet_name=sheet,
                       headers=len(headers),
                       total_rows=len(data_rows))
            
            return result
            
        except Exception as e:
            raise ValueError(f"Failed to parse XLSX file: {str(e)}")
    
    def _parse_xls(self, file_content: bytes, sheet_name: Optional[str], max_rows: int) -> Dict[str, Any]:
        """Parse XLS file."""
        try:
            # Read with pandas
            excel_file = pd.ExcelFile(io.BytesIO(file_content))
            
            # Use specified sheet or first sheet
            sheet = sheet_name or excel_file.sheet_names[0]
            
            if sheet not in excel_file.sheet_names:
                raise ValueError(f"Sheet '{sheet}' not found in workbook")
            
            # Read data
            df = pd.read_excel(excel_file, sheet_name=sheet, nrows=max_rows)
            
            # Convert to list of lists
            headers = [str(col) for col in df.columns]
            data_rows = df.values.tolist()
            
            # Handle duplicate headers
            headers = self._deduplicate_headers(headers)
            
            # Generate column statistics
            column_stats = self._generate_column_stats(data_rows, len(headers))
            
            result = {
                'success': True,
                'sheet_name': sheet,
                'available_sheets': excel_file.sheet_names,
                'headers': headers,
                'total_rows': len(data_rows),
                'preview_rows': data_rows,
                'column_stats': column_stats,
                'formula_issues': [],  # XLS doesn't have cached formula issues like XLSX
                'file_type': 'xls'
            }
            
            logger.info("XLS parsed successfully", 
                       sheet_name=sheet,
                       headers=len(headers),
                       total_rows=len(data_rows))
            
            return result
            
        except Exception as e:
            raise ValueError(f"Failed to parse XLS file: {str(e)}")
    
    def _deduplicate_headers(self, headers: List[str]) -> List[str]:
        """Ensure unique headers while preserving display names."""
        seen = {}
        result = []
        
        for header in headers:
            if header in seen:
                seen[header] += 1
                result.append(f"{header}_{seen[header]}")
            else:
                seen[header] = 0
                result.append(header)
        
        return result
    
    def _generate_column_stats(self, data_rows: List[List[Any]], num_columns: int) -> List[Dict[str, Any]]:
        """Generate statistics for each column."""
        stats = []
        
        for col_idx in range(num_columns):
            column_values = []
            for row in data_rows:
                if col_idx < len(row):
                    column_values.append(str(row[col_idx]) if row[col_idx] is not None else '')
            
            stats.append({
                'column_index': col_idx,
                'non_empty_count': len([v for v in column_values if v.strip()]),
                'empty_count': len([v for v in column_values if not v.strip()]),
                'unique_count': len(set(column_values)),
                'sample_values': column_values[:5] if column_values else []
            })
        
        return stats
    
    def _check_formula_issues(self, file_content: bytes, sheet_name: str) -> List[Dict[str, Any]]:
        """Check for formula-related issues in XLSX files."""
        issues = []
        
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(file_content), read_only=False)
            
            if sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                
                # Check for cells with formulas but no cached values
                for row in worksheet.iter_rows():
                    for cell in row:
                        if cell.data_type == 'f':  # Formula
                            if cell.value is None:
                                issues.append({
                                    'type': 'missing_cached_value',
                                    'cell': cell.coordinate,
                                    'description': 'Formula has no cached value'
                                })
                
                workbook.close()
                
        except Exception as e:
            logger.warning("Could not check formula issues", error=str(e))
        
        return issues


# Global Excel parser instance
excel_parser = ExcelParser()
