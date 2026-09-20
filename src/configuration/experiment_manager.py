"""Experiment configuration management."""
import uuid
from typing import List, Dict, Any, Optional
from enum import Enum

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__)


class ClassificationType(Enum):
    """Classification type enumeration."""
    SENTIMENT = "sentiment"
    TOPIC = "topic"
    CATEGORY = "category"
    CUSTOM = "custom"
    UNDEFINED = "undefined"


class ExperimentConfigManager:
    """Manages experiment configurations and versions."""
    
    def __init__(self):
        self.configurations = {}  # In-memory storage for now
    
    def create_experiment_config(self, name: str, config_data: Dict[str, Any], 
                               user_id: str, description: str = None) -> Dict[str, Any]:
        """Create a new experiment configuration version."""
        try:
            config_id = str(uuid.uuid4())
            
            # Validate configuration
            validation_result = self._validate_config(config_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            # Create configuration
            config = {
                'id': config_id,
                'name': name,
                'description': description or '',
                'config': config_data,
                'created_by': user_id,
                'created_at': self._get_timestamp(),
                'version': 1,
                'parent_version_id': None,
                'is_active': True
            }
            
            self.configurations[config_id] = config
            
            logger.info("Experiment config created", 
                       config_id=config_id,
                       name=name)
            
            return {
                'success': True,
                'config_id': config_id,
                'config': config
            }
            
        except Exception as e:
            logger.error("Failed to create experiment config", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_config_version(self, parent_id: str, updates: Dict[str, Any], 
                            user_id: str) -> Dict[str, Any]:
        """Create a new version of an existing configuration."""
        try:
            if parent_id not in self.configurations:
                return {
                    'success': False,
                    'error': 'Parent configuration not found'
                }
            
            parent_config = self.configurations[parent_id]
            new_version_id = str(uuid.uuid4())
            
            # Merge updates with parent data
            new_config_data = parent_config['config'].copy()
            new_config_data.update(updates.get('config', {}))
            
            # Validate updated configuration
            validation_result = self._validate_config(new_config_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            # Create new version
            new_version = {
                'id': new_version_id,
                'name': updates.get('name', parent_config['name']),
                'description': updates.get('description', parent_config['description']),
                'config': new_config_data,
                'created_by': user_id,
                'created_at': self._get_timestamp(),
                'version': parent_config['version'] + 1,
                'parent_version_id': parent_id,
                'is_active': True
            }
            
            # Deactivate parent
            parent_config['is_active'] = False
            
            self.configurations[new_version_id] = new_version
            
            logger.info("Experiment config version created", 
                       new_version_id=new_version_id,
                       parent_version_id=parent_id,
                       version=new_version['version'])
            
            return {
                'success': True,
                'config_id': new_version_id,
                'config': new_version
            }
            
        except Exception as e:
            logger.error("Failed to create config version", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_experiment_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Get experiment configuration by ID."""
        return self.configurations.get(config_id)
    
    def get_active_configs(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active configurations for a user."""
        return [
            cfg for cfg in self.configurations.values()
            if cfg['created_by'] == user_id and cfg['is_active']
        ]

    def set_draft_taxonomy(self, config_id: str, taxonomy: Dict[str, Any]) -> bool:
        """Persist a discovered draft taxonomy onto a stored configuration."""
        stored = self.configurations.get(config_id)
        if not stored:
            return False
        stored['config']['draft_taxonomy'] = taxonomy
        logger.info("Draft taxonomy stored on configuration",
                    config_id=config_id,
                    taxonomy_id=taxonomy.get('id'),
                    version=taxonomy.get('version'))
        return True
    
    def _validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate experiment configuration."""
        required_fields = [
            'classification_type',
            'input_fields',
            'output_format',
            'max_tokens',
            'temperature'
        ]
        
        # Check required fields
        for field in required_fields:
            if field not in config_data:
                return {
                    'valid': False,
                    'error': f'Missing required field: {field}'
                }
        
        # Validate classification type
        if config_data['classification_type'] not in [t.value for t in ClassificationType]:
            return {
                'valid': False,
                'error': f'Invalid classification type: {config_data["classification_type"]}'
            }
        
        # Validate input fields
        if not isinstance(config_data['input_fields'], list) or not config_data['input_fields']:
            return {
                'valid': False,
                'error': 'input_fields must be a non-empty list'
            }
        
        # Validate output format
        valid_formats = ['json', 'text', 'structured']
        if config_data['output_format'] not in valid_formats:
            return {
                'valid': False,
                'error': f'Invalid output format: {config_data["output_format"]}'
            }
        
        # Validate numeric fields
        if not isinstance(config_data['max_tokens'], int) or config_data['max_tokens'] <= 0:
            return {
                'valid': False,
                'error': 'max_tokens must be a positive integer'
            }
        
        if not isinstance(config_data['temperature'], (int, float)) or not 0 <= config_data['temperature'] <= 2:
            return {
                'valid': False,
                'error': 'temperature must be a number between 0 and 2'
            }
        
        # Validate optional fields
        if 'category_set_id' in config_data:
            try:
                uuid.UUID(config_data['category_set_id'])
            except ValueError:
                return {
                    'valid': False,
                    'error': 'category_set_id must be a valid UUID'
                }
        
        if 'batch_size' in config_data:
            if not isinstance(config_data['batch_size'], int) or config_data['batch_size'] <= 0:
                return {
                    'valid': False,
                    'error': 'batch_size must be a positive integer'
                }
        
        # Undefined classification has no accepted taxonomy; the preview
        # model proposes draft categories later. Requires objective and
        # label mode instead of a category set.
        if config_data['classification_type'] == ClassificationType.UNDEFINED.value:
            objective = config_data.get('objective')
            if not isinstance(objective, str) or not objective.strip():
                return {
                    'valid': False,
                    'error': 'objective is required for undefined classification'
                }
            if config_data.get('label_mode') not in ['single_label', 'multi_label']:
                return {
                    'valid': False,
                    'error': 'label_mode must be single_label or multi_label'
                }
            output_fields = config_data.get('output_fields')
            if not isinstance(output_fields, list) or not output_fields:
                return {
                    'valid': False,
                    'error': 'output_fields must be a non-empty list'
                }
        
        return {'valid': True}
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def build_request_payload(self, config_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build request payload for classification."""
        config = self.get_experiment_config(config_id)
        if not config:
            return {
                'success': False,
                'error': 'Configuration not found'
            }
        
        try:
            # Build request based on classification type
            classification_type = config['config']['classification_type']
            
            if classification_type == 'sentiment':
                payload = self._build_sentiment_request(config, input_data)
            elif classification_type == 'topic':
                payload = self._build_topic_request(config, input_data)
            elif classification_type == 'category':
                payload = self._build_category_request(config, input_data)
            else:
                payload = self._build_custom_request(config, input_data)
            
            logger.info("Request payload built", 
                       config_id=config_id,
                       classification_type=classification_type)
            
            return {
                'success': True,
                'payload': payload
            }
            
        except Exception as e:
            logger.error("Failed to build request payload", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_sentiment_request(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build sentiment classification request."""
        return {
            'model': get_settings().openai_model_name,
            'messages': [
                {
                    'role': 'system',
                    'content': 'Classify the sentiment of the following review as positive, negative, or neutral.'
                },
                {
                    'role': 'user',
                    'content': input_data.get('review_text', '')
                }
            ],
            'max_tokens': config['config']['max_tokens'],
            'temperature': config['config']['temperature'],
            'response_format': {'type': 'json_object'}
        }
    
    def _build_topic_request(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build topic classification request."""
        return {
            'model': get_settings().openai_model_name,
            'messages': [
                {
                    'role': 'system',
                    'content': 'Classify the main topic of the following review.'
                },
                {
                    'role': 'user',
                    'content': input_data.get('review_text', '')
                }
            ],
            'max_tokens': config['config']['max_tokens'],
            'temperature': config['config']['temperature'],
            'response_format': {'type': 'json_object'}
        }
    
    def _build_category_request(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build category classification request."""
        # This would use the category_set_id to get categories
        return {
            'model': get_settings().openai_model_name,
            'messages': [
                {
                    'role': 'system',
                    'content': 'Classify the following review into the appropriate category.'
                },
                {
                    'role': 'user',
                    'content': input_data.get('review_text', '')
                }
            ],
            'max_tokens': config['config']['max_tokens'],
            'temperature': config['config']['temperature'],
            'response_format': {'type': 'json_object'}
        }
    
    def _build_custom_request(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build custom classification request."""
        return {
            'model': get_settings().openai_model_name,
            'messages': [
                {
                    'role': 'system',
                    'content': config['config'].get('system_prompt', 'Classify the following review.')
                },
                {
                    'role': 'user',
                    'content': input_data.get('review_text', '')
                }
            ],
            'max_tokens': config['config']['max_tokens'],
            'temperature': config['config']['temperature'],
            'response_format': {'type': 'json_object'}
        }


# Global experiment config manager instance
experiment_manager = ExperimentConfigManager()
