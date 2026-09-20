"""Request contract validation for classification APIs."""
from typing import Dict, Any, List
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class ContractType(Enum):
    """Request contract type."""
    CLASSIFICATION_REQUEST = "classification_request"
    CATEGORY_DEFINITION = "category_definition"
    EXPERIMENT_CONFIG = "experiment_config"


class RequestContractValidator:
    """Validates request contracts for classification APIs."""
    
    def __init__(self):
        self.contracts = self._define_contracts()
    
    def _define_contracts(self) -> Dict[str, Dict[str, Any]]:
        """Define request contracts."""
        return {
            ContractType.CLASSIFICATION_REQUEST.value: {
                'required_fields': ['config_id', 'input_data'],
                'optional_fields': ['metadata', 'request_id'],
                'field_types': {
                    'config_id': str,
                    'input_data': dict,
                    'metadata': dict,
                    'request_id': str
                },
                'field_constraints': {
                    'config_id': {'uuid': True},
                    'input_data': {'required_fields': ['review_text']}
                }
            },
            ContractType.CATEGORY_DEFINITION.value: {
                'required_fields': ['name', 'categories'],
                'optional_fields': ['description', 'parent_version_id'],
                'field_types': {
                    'name': str,
                    'categories': list,
                    'description': str,
                    'parent_version_id': str
                },
                'field_constraints': {
                    'categories': {
                        'min_items': 1,
                        'item_type': dict,
                        'required_fields': ['id', 'name', 'type']
                    }
                }
            },
            ContractType.EXPERIMENT_CONFIG.value: {
                'required_fields': ['name', 'config'],
                'optional_fields': ['description', 'parent_version_id'],
                'field_types': {
                    'name': str,
                    'config': dict,
                    'description': str,
                    'parent_version_id': str
                },
                'field_constraints': {
                    'config': {
                        'required_fields': [
                            'classification_type',
                            'input_fields',
                            'output_format',
                            'max_tokens',
                            'temperature'
                        ]
                    }
                }
            }
        }
    
    def validate_request(self, contract_type: ContractType, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate request against contract."""
        try:
            contract = self.contracts.get(contract_type.value)
            if not contract:
                return {
                    'valid': False,
                    'error': f'Unknown contract type: {contract_type.value}'
                }
            
            errors = []
            warnings = []
            
            # Check required fields
            for field in contract['required_fields']:
                if field not in request_data:
                    errors.append(f'Missing required field: {field}')
                elif request_data[field] is None:
                    errors.append(f'Required field cannot be null: {field}')
            
            # Check field types
            for field, value in request_data.items():
                if field in contract['field_types']:
                    expected_type = contract['field_types'][field]
                    if not isinstance(value, expected_type):
                        errors.append(f'Field {field} must be {expected_type.__name__}, got {type(value).__name__}')
                elif field not in contract['optional_fields']:
                    warnings.append(f'Unknown field: {field}')
            
            # Check field constraints
            for field, constraints in contract['field_constraints'].items():
                if field in request_data:
                    constraint_errors = self._validate_field_constraints(field, request_data[field], constraints)
                    errors.extend(constraint_errors)
            
            # Validate UUID fields
            for field in ['config_id', 'parent_version_id', 'category_set_id']:
                if field in request_data and request_data[field]:
                    if not self._is_valid_uuid(request_data[field]):
                        errors.append(f'Field {field} must be a valid UUID')
            
            result = {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'contract_type': contract_type.value
            }
            
            if errors:
                logger.warning("Request contract validation failed", 
                             contract_type=contract_type.value,
                             errors=errors)
            else:
                logger.info("Request contract validation passed", 
                           contract_type=contract_type.value)
            
            return result
            
        except Exception as e:
            logger.error("Contract validation error", error=str(e))
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }
    
    def _validate_field_constraints(self, field_name: str, value: Any, constraints: Dict[str, Any]) -> List[str]:
        """Validate field-specific constraints."""
        errors = []
        
        # UUID validation
        if constraints.get('uuid') and not self._is_valid_uuid(value):
            errors.append(f'Field {field_name} must be a valid UUID')
        
        # Required fields in nested objects
        if 'required_fields' in constraints:
            if isinstance(value, dict):
                for req_field in constraints['required_fields']:
                    if req_field not in value:
                        errors.append(f'Field {field_name}.{req_field} is required')
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for req_field in constraints['required_fields']:
                            if req_field not in item:
                                errors.append(f'Field {field_name}[{i}].{req_field} is required')
        
        # List constraints
        if 'min_items' in constraints:
            if isinstance(value, list) and len(value) < constraints['min_items']:
                errors.append(f'Field {field_name} must have at least {constraints["min_items"]} items')
        
        if 'max_items' in constraints:
            if isinstance(value, list) and len(value) > constraints['max_items']:
                errors.append(f'Field {field_name} must have at most {constraints["max_items"]} items')
        
        # Item type validation
        if 'item_type' in constraints:
            if isinstance(value, list):
                expected_type = constraints['item_type']
                for i, item in enumerate(value):
                    if not isinstance(item, expected_type):
                        errors.append(f'Field {field_name}[{i}] must be {expected_type.__name__}')
        
        return errors
    
    def _is_valid_uuid(self, value: Any) -> bool:
        """Check if value is a valid UUID."""
        if not isinstance(value, str):
            return False
        try:
            import uuid
            uuid.UUID(value)
            return True
        except ValueError:
            return False
    
    def get_contract_schema(self, contract_type: ContractType) -> Dict[str, Any]:
        """Get contract schema for documentation."""
        contract = self.contracts.get(contract_type.value)
        if not contract:
            return {
                'success': False,
                'error': f'Unknown contract type: {contract_type.value}'
            }
        
        return {
            'success': True,
            'contract_type': contract_type.value,
            'schema': contract
        }
    
    def list_contracts(self) -> Dict[str, Any]:
        """List all available contracts."""
        return {
            'success': True,
            'contracts': list(self.contracts.keys())
        }


# Global contract validator instance
contract_validator = RequestContractValidator()
