"""Eligibility screening for review data."""
from typing import List, Dict, Any, Optional
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class EligibilityReason(Enum):
    BLANK_TEXT = "blank_text"
    NON_TEXT_VALUE = "non_text_value"
    DUPLICATE_TEXT = "duplicate_text"
    LANGUAGE_UNSUPPORTED = "language_unsupported"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    INVALID_FORMAT = "invalid_format"
    MISSING_REQUIRED_FIELD = "missing_required_field"


class EligibilityScreener:
    """Screens review records for eligibility issues."""
    
    def __init__(self):
        self.min_text_length = 1
        self.max_text_length = 50000
        self.supported_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh']
        self.duplicate_threshold = 0.95  # Similarity threshold for duplicates
    
    def screen_records(self, records: List[Dict[str, Any]], 
                      field_mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Screen records for eligibility issues."""
        results = {
            'total_records': len(records),
            'eligible_records': 0,
            'excluded_records': 0,
            'eligibility_reasons': {},
            'issues': []
        }
        
        # Get review text field name
        review_text_field = self._get_review_text_field(field_mapping)
        
        for i, record in enumerate(records):
            eligibility_result = self._check_record_eligibility(record, field_mapping, review_text_field, i)
            
            if eligibility_result['eligible']:
                results['eligible_records'] += 1
            else:
                results['excluded_records'] += 1
                reason = eligibility_result['reason']
                results['eligibility_reasons'][reason] = results['eligibility_reasons'].get(reason, 0) + 1
                
                results['issues'].append({
                    'record_index': i,
                    'record_id': record.get('id', f'row_{i}'),
                    'reason': reason,
                    'description': eligibility_result['description'],
                    'suggestion': eligibility_result.get('suggestion', '')
                })
        
        results['eligibility_rate'] = (results['eligible_records'] / results['total_records']) * 100 if results['total_records'] > 0 else 0
        
        logger.info("Eligibility screening completed", 
                   total=results['total_records'],
                   eligible=results['eligible_records'],
                   excluded=results['excluded_records'],
                   eligibility_rate=results['eligibility_rate'])
        
        return results
    
    def _check_record_eligibility(self, record: Dict[str, Any], 
                                field_mapping: Dict[str, Any], 
                                review_text_field: Optional[str],
                                record_index: int) -> Dict[str, Any]:
        """Check individual record eligibility."""
        # Check if review text field is mapped
        if not review_text_field:
            return {
                'eligible': False,
                'reason': EligibilityReason.MISSING_REQUIRED_FIELD.value,
                'description': 'No review text field mapped',
                'suggestion': 'Map a column to review text'
            }
        
        # Get review text
        review_text = record.get('original_review_text', '')
        if not review_text:
            review_text = record.get('mapped_metadata', {}).get(review_text_field, '')
        
        # Check for blank text
        if not review_text or not str(review_text).strip():
            return {
                'eligible': False,
                'reason': EligibilityReason.BLANK_TEXT.value,
                'description': 'Review text is empty or contains only whitespace',
                'suggestion': 'Check data source for missing values'
            }
        
        # Check text length
        text_length = len(str(review_text).strip())
        if text_length < self.min_text_length:
            return {
                'eligible': False,
                'reason': EligibilityReason.TOO_SHORT.value,
                'description': f'Review text too short ({text_length} characters)',
                'suggestion': f'Minimum length is {self.min_text_length} characters'
            }
        
        if text_length > self.max_text_length:
            return {
                'eligible': False,
                'reason': EligibilityReason.TOO_LONG.value,
                'description': f'Review text too long ({text_length} characters)',
                'suggestion': f'Maximum length is {self.max_text_length} characters'
            }
        
        # Check for non-text values
        if not isinstance(review_text, str):
            return {
                'eligible': False,
                'reason': EligibilityReason.NON_TEXT_VALUE.value,
                'description': 'Review text is not a string value',
                'suggestion': 'Convert to text format'
            }
        
        # Check for numeric-only text
        if str(review_text).strip().isdigit():
            return {
                'eligible': False,
                'reason': EligibilityReason.NON_TEXT_VALUE.value,
                'description': 'Review text contains only numbers',
                'suggestion': 'Check if this is a valid review'
            }
        
        # Check language if language field is mapped
        language_field = self._get_language_field(field_mapping)
        if language_field:
            language = record.get('mapped_metadata', {}).get(language_field, '')
            if language and language.lower() not in self.supported_languages:
                return {
                    'eligible': False,
                    'reason': EligibilityReason.LANGUAGE_UNSUPPORTED.value,
                    'description': f'Language "{language}" not supported',
                    'suggestion': f'Supported languages: {", ".join(self.supported_languages)}'
                }
        
        # Check for duplicates (basic check)
        if self._is_duplicate_text(review_text, record_index):
            return {
                'eligible': False,
                'reason': EligibilityReason.DUPLICATE_TEXT.value,
                'description': 'Review text appears to be a duplicate',
                'suggestion': 'Review for duplicate content'
            }
        
        return {
            'eligible': True,
            'reason': None,
            'description': 'Record meets all eligibility criteria'
        }
    
    def check_record(self, record: Dict[str, Any],
                     field_mapping: Dict[str, Any],
                     record_index: int = 0) -> bool:
        """Check whether a single record is eligible."""
        review_text_field = self._get_review_text_field(field_mapping)
        return self._check_record_eligibility(
            record, field_mapping, review_text_field, record_index
        )['eligible']

    def _get_review_text_field(self, field_mapping: Dict[str, Any]) -> Optional[str]:
        """Get the field name mapped to review text."""
        for field_name, field_type in field_mapping.items():
            if field_type == 'review_text':
                return field_name
        return None
    
    def _get_language_field(self, field_mapping: Dict[str, Any]) -> Optional[str]:
        """Get the field name mapped to language."""
        for field_name, field_type in field_mapping.items():
            if field_type == 'language':
                return field_name
        return None
    
    def _is_duplicate_text(self, text: str, record_index: int) -> bool:
        """Check if text is likely a duplicate (simplified check)."""
        # This is a simplified check - in production, you'd use more sophisticated similarity detection
        text_lower = str(text).lower().strip()
        
        # Check for very short generic responses
        generic_responses = [
            'good', 'bad', 'ok', 'okay', 'yes', 'no', 'great', 'terrible',
            'excellent', 'awful', 'nice', 'poor', 'average', 'mediocre'
        ]
        
        if text_lower in generic_responses:
            return True
        
        # Check for very short text that might be spam
        if len(text_lower) < 3:
            return True
        
        return False
    
    def get_eligibility_summary(self, records: List[Dict[str, Any]], 
                              field_mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary of eligibility screening."""
        screening_result = self.screen_records(records, field_mapping)
        
        return {
            'total_records': screening_result['total_records'],
            'eligible_count': screening_result['eligible_records'],
            'excluded_count': screening_result['excluded_records'],
            'eligibility_rate': screening_result['eligibility_rate'],
            'exclusion_reasons': screening_result['eligibility_reasons'],
            'top_issues': screening_result['issues'][:10]  # Top 10 issues
        }


# Global eligibility screener instance
eligibility_screener = EligibilityScreener()
