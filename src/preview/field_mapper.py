"""Field mapping for review data."""
from typing import List, Dict, Any, Optional
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class FieldType(Enum):
    REVIEW_TEXT = "review_text"
    RECORD_ID = "record_id"
    TIMESTAMP = "timestamp"
    RATING = "rating"
    LANGUAGE = "language"
    PRODUCT = "product"
    SOURCE = "source"
    OTHER = "other"


class FieldMapping:
    """Manages field mapping for review data."""
    
    def __init__(self):
        self.required_fields = [FieldType.REVIEW_TEXT]
        self.optional_fields = [
            FieldType.RECORD_ID,
            FieldType.TIMESTAMP,
            FieldType.RATING,
            FieldType.LANGUAGE,
            FieldType.PRODUCT,
            FieldType.SOURCE
        ]
    
    def suggest_mappings(self, headers: List[str], sample_data: List[List[str]]) -> Dict[str, FieldType]:
        """Suggest field mappings based on column names and sample data."""
        suggestions = {}
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            sample_values = [row[i] for row in sample_data[:10] if i < len(row)]
            
            # Suggest review text field
            if self._is_text_field(header_lower, sample_values):
                suggestions[header] = FieldType.REVIEW_TEXT
            elif self._is_id_field(header_lower, sample_values):
                suggestions[header] = FieldType.RECORD_ID
            elif self._is_timestamp_field(header_lower, sample_values):
                suggestions[header] = FieldType.TIMESTAMP
            elif self._is_rating_field(header_lower, sample_values):
                suggestions[header] = FieldType.RATING
            elif self._is_language_field(header_lower, sample_values):
                suggestions[header] = FieldType.LANGUAGE
            elif self._is_product_field(header_lower, sample_values):
                suggestions[header] = FieldType.PRODUCT
            elif self._is_source_field(header_lower, sample_values):
                suggestions[header] = FieldType.SOURCE
            else:
                suggestions[header] = FieldType.OTHER
        
        logger.info("Field mapping suggestions generated", 
                   total_fields=len(headers),
                   suggested_mappings=len([k for k, v in suggestions.items() if v != FieldType.OTHER]))
        
        return suggestions
    
    def _is_text_field(self, header: str, values: List[str]) -> bool:
        """Check if field is likely review text."""
        text_indicators = ['text', 'review', 'comment', 'content', 'description', 'body', 'feedback', 'message']
        
        # Check header name
        if any(indicator in header for indicator in text_indicators):
            return True
        
        # Check sample values for text characteristics
        if values:
            avg_length = sum(len(str(v)) for v in values if v) / len(values)
            if avg_length > 50:  # Long text likely to be review
                return True
        
        return False
    
    def _is_id_field(self, header: str, values: List[str]) -> bool:
        """Check if field is likely a record ID."""
        id_indicators = ['id', 'identifier', 'key', 'ref', 'reference', 'code']
        
        # Check header name
        if any(indicator in header for indicator in id_indicators):
            return True
        
        # Check sample values for ID characteristics
        if values:
            # Check if values are unique and not too long
            unique_values = set(values)
            if len(unique_values) == len(values) and len(values) > 0:
                avg_length = sum(len(str(v)) for v in values if v) / len(values)
                if avg_length < 50:  # Short unique values likely to be IDs
                    return True
        
        return False
    
    def _is_timestamp_field(self, header: str, values: List[str]) -> bool:
        """Check if field is likely a timestamp."""
        timestamp_indicators = ['date', 'time', 'created', 'modified', 'timestamp', 'datetime']
        
        # Check header name
        if any(indicator in header for indicator in timestamp_indicators):
            return True
        
        # Check sample values for date patterns
        if values:
            date_patterns = ['-', '/', ':', 'T', 'Z']
            for value in values:
                if value and any(pattern in str(value) for pattern in date_patterns):
                    return True
        
        return False
    
    def _is_rating_field(self, header: str, values: List[str]) -> bool:
        """Check if field is likely a rating."""
        rating_indicators = ['rating', 'score', 'stars', 'grade', 'rank', 'evaluation']
        
        # Check header name
        if any(indicator in header for indicator in rating_indicators):
            return True
        
        # Check sample values for numeric patterns
        if values:
            numeric_count = 0
            for value in values:
                if value and str(value).replace('.', '').replace('-', '').isdigit():
                    numeric_count += 1
            
            if numeric_count > len(values) * 0.7:  # Mostly numeric
                return True
        
        return False
    
    def _is_language_field(self, header: str, values: List[str]) -> bool:
        """Check if field is likely a language."""
        language_indicators = ['language', 'lang', 'locale', 'locale_code']
        
        # Check header name
        if any(indicator in header for indicator in language_indicators):
            return True
        
        # Check sample values for language codes
        if values:
            language_codes = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh']
            for value in values:
                if value and str(value).lower() in language_codes:
                    return True
        
        return False
    
    def _is_product_field(self, header: str, values: List[str]) -> bool:
        """Check if field is likely a product."""
        product_indicators = ['product', 'item', 'sku', 'model', 'version', 'name']
        
        # Check header name
        if any(indicator in header for indicator in product_indicators):
            return True
        
        return False
    
    def _is_source_field(self, header: str, values: List[str]) -> bool:
        """Check if field is likely a source."""
        source_indicators = ['source', 'origin', 'channel', 'platform', 'site', 'url']
        
        # Check header name
        if any(indicator in header for indicator in source_indicators):
            return True
        
        return False
    
    def validate_mapping(self, mapping: Dict[str, FieldType], headers: List[str]) -> Dict[str, Any]:
        """Validate field mapping."""
        errors = []
        warnings = []
        
        # Check required fields
        mapped_types = set(mapping.values())
        for required_field in self.required_fields:
            if required_field not in mapped_types:
                errors.append(f"Required field '{required_field.value}' is not mapped")
        
        # Check for duplicate mappings
        for field_type in FieldType:
            mapped_headers = [h for h, t in mapping.items() if t == field_type]
            if len(mapped_headers) > 1:
                warnings.append(f"Multiple headers mapped to '{field_type.value}': {', '.join(mapped_headers)}")
        
        # Check if all headers are mapped
        unmapped_headers = [h for h in headers if h not in mapping]
        if unmapped_headers:
            warnings.append(f"Unmapped headers: {', '.join(unmapped_headers)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'mapped_fields': len([k for k, v in mapping.items() if v != FieldType.OTHER]),
            'unmapped_fields': len(unmapped_headers)
        }
    
    def get_mapping_summary(self, mapping: Dict[str, FieldType]) -> Dict[str, Any]:
        """Get summary of field mapping."""
        field_counts = {}
        for field_type in FieldType:
            field_counts[field_type.value] = len([k for k, v in mapping.items() if v == field_type])
        
        return {
            'field_counts': field_counts,
            'total_mapped': len([k for k, v in mapping.items() if v != FieldType.OTHER]),
            'required_mapped': field_counts[FieldType.REVIEW_TEXT.value] > 0,
            'optional_mapped': sum(field_counts[ft.value] for ft in self.optional_fields)
        }


# Global field mapper instance
field_mapper = FieldMapping()
