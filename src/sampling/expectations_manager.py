"""Expectations management for classification preview."""
import uuid
from typing import List, Dict, Any, Optional
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class ExpectationType(Enum):
    """Expectation type."""
    PRIMARY_CATEGORY = "primary_category"
    SECONDARY_CATEGORY = "secondary_category"
    SENTIMENT = "sentiment"
    CONFIDENCE = "confidence"
    EXPECTED_THEME = "expected_theme"
    CUSTOM = "custom"


class ExpectationStatus(Enum):
    """Expectation status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    PARTIAL = "partial"


class ExpectationsManager:
    """Manages user expectations for classification results."""
    
    def __init__(self):
        self.expectations = {}  # In-memory storage for now
    
    def create_expectation_set(self, sample_id: str, expectations: List[Dict[str, Any]], 
                              user_id: str, description: str = None) -> Dict[str, Any]:
        """Create a new expectation set for a sample."""
        try:
            expectation_set_id = str(uuid.uuid4())
            
            # Validate expectations
            validation_result = self._validate_expectations(expectations)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            # Create expectation set
            expectation_set = {
                'id': expectation_set_id,
                'sample_id': sample_id,
                'expectations': expectations,
                'created_by': user_id,
                'created_at': self._get_timestamp(),
                'description': description or '',
                'status': ExpectationStatus.PENDING.value,
                'is_active': True
            }
            
            self.expectations[expectation_set_id] = expectation_set
            
            logger.info("Expectation set created", 
                       expectation_set_id=expectation_set_id,
                       sample_id=sample_id,
                       expectation_count=len(expectations))
            
            return {
                'success': True,
                'expectation_set_id': expectation_set_id,
                'expectation_set': expectation_set
            }
            
        except Exception as e:
            logger.error("Failed to create expectation set", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_expectation(self, expectation_set_id: str, expectation_id: str, 
                          updates: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Update a specific expectation."""
        try:
            if expectation_set_id not in self.expectations:
                return {
                    'success': False,
                    'error': 'Expectation set not found'
                }
            
            expectation_set = self.expectations[expectation_set_id]
            
            # Find and update the expectation
            updated = False
            for i, exp in enumerate(expectation_set['expectations']):
                if exp.get('id') == expectation_id:
                    expectation_set['expectations'][i].update(updates)
                    expectation_set['expectations'][i]['updated_at'] = self._get_timestamp()
                    updated = True
                    break
            
            if not updated:
                return {
                    'success': False,
                    'error': 'Expectation not found'
                }
            
            logger.info("Expectation updated", 
                       expectation_set_id=expectation_set_id,
                       expectation_id=expectation_id)
            
            return {
                'success': True,
                'expectation_set': expectation_set
            }
            
        except Exception as e:
            logger.error("Failed to update expectation", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_expectation_set(self, expectation_set_id: str) -> Optional[Dict[str, Any]]:
        """Get expectation set by ID."""
        return self.expectations.get(expectation_set_id)
    
    def get_sample_expectations(self, sample_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get all expectation sets for a sample."""
        return [
            exp for exp in self.expectations.values()
            if exp['sample_id'] == sample_id and exp['created_by'] == user_id
        ]
    
    def _validate_expectations(self, expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate expectation structure."""
        if not expectations:
            return {'valid': False, 'error': 'At least one expectation is required'}
        
        required_fields = ['record_id', 'type', 'expected_value']
        
        for i, expectation in enumerate(expectations):
            # Check required fields
            for field in required_fields:
                if field not in expectation:
                    return {
                        'valid': False,
                        'error': f'Expectation {i+1} missing required field: {field}'
                    }
            
            # Validate expectation type
            if expectation['type'] not in [t.value for t in ExpectationType]:
                return {
                    'valid': False,
                    'error': f'Expectation {i+1} has invalid type: {expectation["type"]}'
                }
            
            # Validate record_id is present
            if not expectation['record_id']:
                return {
                    'valid': False,
                    'error': f'Expectation {i+1} must have record_id'
                }
            
            # Add unique ID if not present
            if 'id' not in expectation:
                expectation['id'] = str(uuid.uuid4())
            
            # Set default status
            if 'status' not in expectation:
                expectation['status'] = ExpectationStatus.PENDING.value
        
        return {'valid': True}
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def create_expectation_template(self, sample_records: List[Dict[str, Any]], 
                                   expectation_type: ExpectationType) -> Dict[str, Any]:
        """Create expectation template for a sample."""
        try:
            template = {
                'type': expectation_type.value,
                'suggestions': [],
                'field_mapping': {},
                'confidence_levels': ['high', 'medium', 'low']
            }
            
            # Generate suggestions based on type
            if expectation_type == ExpectationType.PRIMARY_CATEGORY:
                template['suggestions'] = self._get_category_suggestions(sample_records)
            elif expectation_type == ExpectationType.SENTIMENT:
                template['suggestions'] = ['positive', 'negative', 'neutral']
            elif expectation_type == ExpectationType.CONFIDENCE:
                template['suggestions'] = ['high', 'medium', 'low']
            
            # Create field mapping suggestions
            template['field_mapping'] = {
                'record_id': 'id',
                'expected_value': 'expected_category',
                'confidence': 'confidence_level',
                'notes': 'expectation_notes'
            }
            
            logger.info("Expectation template created", 
                       type=expectation_type.value,
                       suggestion_count=len(template['suggestions']))
            
            return {
                'success': True,
                'template': template
            }
            
        except Exception as e:
            logger.error("Failed to create expectation template", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_category_suggestions(self, sample_records: List[Dict[str, Any]]) -> List[str]:
        """Get category suggestions from sample records."""
        # Extract potential categories from existing data
        categories = set()
        
        for record in sample_records:
            # Look for category-like fields
            for field in ['category', 'product_category', 'type', 'sentiment']:
                value = record.get(field)
                if value and isinstance(value, str):
                    categories.add(value.lower())
        
        # Add common categories if none found
        if not categories:
            categories = {'positive', 'negative', 'neutral', 'mixed'}
        
        return sorted(list(categories))
    
    def validate_expectation_coverage(self, expectation_set_id: str) -> Dict[str, Any]:
        """Validate expectation coverage for a sample."""
        try:
            expectation_set = self.get_expectation_set(expectation_set_id)
            if not expectation_set:
                return {
                    'valid': False,
                    'error': 'Expectation set not found'
                }
            
            expectations = expectation_set['expectations']
            sample_id = expectation_set['sample_id']
            
            # Check coverage
            record_ids = {exp['record_id'] for exp in expectations}
            types_covered = {exp['type'] for exp in expectations}
            
            coverage_analysis = {
                'total_expectations': len(expectations),
                'unique_records': len(record_ids),
                'types_covered': list(types_covered),
                'coverage_percentage': (len(record_ids) / len(expectations)) * 100 if expectations else 0,
                'missing_types': [t.value for t in ExpectationType if t.value not in types_covered]
            }
            
            return {
                'valid': True,
                'coverage': coverage_analysis
            }
            
        except Exception as e:
            logger.error("Failed to validate expectation coverage", error=str(e))
            return {
                'valid': False,
                'error': str(e)
            }
    
    def get_expectation_summary(self, expectation_set_id: str) -> Dict[str, Any]:
        """Get summary of expectation set."""
        try:
            expectation_set = self.get_expectation_set(expectation_set_id)
            if not expectation_set:
                return {
                    'success': False,
                    'error': 'Expectation set not found'
                }
            
            expectations = expectation_set['expectations']
            
            # Calculate summary statistics
            status_counts = {}
            type_counts = {}
            
            for exp in expectations:
                status = exp.get('status', ExpectationStatus.PENDING.value)
                exp_type = exp.get('type', 'unknown')
                
                status_counts[status] = status_counts.get(status, 0) + 1
                type_counts[exp_type] = type_counts.get(exp_type, 0) + 1
            
            summary = {
                'expectation_set_id': expectation_set_id,
                'sample_id': expectation_set['sample_id'],
                'total_expectations': len(expectations),
                'status_distribution': status_counts,
                'type_distribution': type_counts,
                'completion_rate': (status_counts.get(ExpectationStatus.CONFIRMED.value, 0) / len(expectations)) * 100 if expectations else 0,
                'created_at': expectation_set['created_at'],
                'description': expectation_set['description']
            }
            
            return {
                'success': True,
                'summary': summary
            }
            
        except Exception as e:
            logger.error("Failed to get expectation summary", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }


# Global expectations manager instance
expectations_manager = ExpectationsManager()
