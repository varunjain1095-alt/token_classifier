"""CSV file parsing with delimiter and encoding detection."""
import csv
import chardet
import io
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

from src.shared.logger import get_logger

logger = get_logger(__name__)


class CSVParser:
    """Parses CSV files with automatic delimiter and encoding detection."""
    
    def __init__(self):
        self.supported_encodings = ['utf-8', 'utf-16', 'latin-1', 'iso-8859-1', 'cp1252']
        self.supported_delimiters = [',', ';', '\t', '|']
    
    def detect_encoding(self, file_content: bytes) -> str:
        """Detect file encoding."""
        try:
            result = chardet.detect(file_content)
            encoding = result['encoding']
            confidence = result['confidence']
            
            logger.info("Encoding detected", 
                       encoding=encoding, 
                       confidence=confidence)
            
            # Use detected encoding if confidence is high enough
            if confidence > 0.7 and encoding in self.supported_encodings:
                return encoding
            
            # Fallback to UTF-8
            return 'utf-8'
            
        except Exception as e:
            logger.error("Encoding detection failed", error=str(e))
            return 'utf-8'
    
    def detect_delimiter(self, file_content: bytes, encoding: str) -> str:
        """Detect CSV delimiter."""
        try:
            # Decode a sample of the file
            sample_size = min(8192, len(file_content))
            sample = file_content[:sample_size].decode(encoding, errors='ignore')
            
            # Use csv.Sniffer to detect delimiter
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample, delimiters=''.join(self.supported_delimiters)).delimiter
            
            logger.info("Delimiter detected", delimiter=repr(delimiter))
            return delimiter
            
        except Exception as e:
            logger.error("Delimiter detection failed", error=str(e))
            # Default to comma
            return ','
    
    def parse_file(self, file_content: bytes, max_rows: int = 100) -> Dict[str, Any]:
        """Parse CSV file and return preview data."""
        try:
            # Detect encoding
            encoding = self.detect_encoding(file_content)
            
            # Detect delimiter
            delimiter = self.detect_delimiter(file_content, encoding)
            
            # Decode content
            text_content = file_content.decode(encoding, errors='replace')
            
            # Parse CSV
            csv_reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
            rows = list(csv_reader)
            
            if not rows:
                raise ValueError("No data found in CSV file")
            
            # Detect header
            headers, data_rows = self._detect_header(rows)
            
            # Limit rows for preview
            preview_rows = data_rows[:max_rows]
            
            # Generate column statistics
            column_stats = self._generate_column_stats(data_rows, len(headers))
            
            result = {
                'success': True,
                'encoding': encoding,
                'delimiter': delimiter,
                'headers': headers,
                'total_rows': len(data_rows),
                'preview_rows': preview_rows,
                'column_stats': column_stats,
                'file_type': 'csv'
            }
            
            logger.info("CSV parsed successfully", 
                       encoding=encoding,
                       delimiter=repr(delimiter),
                       headers=len(headers),
                       total_rows=len(data_rows),
                       preview_rows=len(preview_rows))
            
            return result
            
        except Exception as e:
            logger.error("CSV parsing failed", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'file_type': 'csv'
            }
    
    def _detect_header(self, rows: List[List[str]]) -> Tuple[List[str], List[List[str]]]:
        """Detect if first row is a header."""
        if not rows:
            return [], []
        
        first_row = rows[0]
        second_row = rows[1] if len(rows) > 1 else []
        
        # Check if first row looks like a header
        # (contains mostly strings and doesn't have numeric patterns)
        is_header = True
        
        # Check if first row has mostly non-numeric values
        numeric_count = 0
        for cell in first_row:
            if self._is_numeric(cell):
                numeric_count += 1
        
        # If more than 50% of first row is numeric, probably not a header
        if numeric_count > len(first_row) * 0.5:
            is_header = False
        
        # Check if second row exists and has different data types
        if len(rows) > 1:
            for i, cell in enumerate(second_row):
                if i < len(first_row) and self._is_numeric(cell) and not self._is_numeric(first_row[i]):
                    is_header = True
                    break
        
        if is_header:
            headers = [str(cell).strip() for cell in first_row]
            data_rows = rows[1:]
        else:
            # Generate column names
            headers = [f'Column_{i+1}' for i in range(len(first_row))]
            data_rows = rows
        
        # Handle duplicate headers
        headers = self._deduplicate_headers(headers)
        
        return headers, data_rows
    
    def _is_numeric(self, value: str) -> bool:
        """Check if value is numeric."""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
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
    
    def _generate_column_stats(self, data_rows: List[List[str]], num_columns: int) -> List[Dict[str, Any]]:
        """Generate statistics for each column."""
        stats = []
        
        for col_idx in range(num_columns):
            column_values = []
            for row in data_rows:
                if col_idx < len(row):
                    column_values.append(row[col_idx])
            
            stats.append({
                'column_index': col_idx,
                'non_empty_count': len([v for v in column_values if v.strip()]),
                'empty_count': len([v for v in column_values if not v.strip()]),
                'unique_count': len(set(column_values)),
                'sample_values': column_values[:5] if column_values else []
            })
        
        return stats


# Global CSV parser instance
csv_parser = CSVParser()
