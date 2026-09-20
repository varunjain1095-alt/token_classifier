"""Category set management for classification."""
import uuid
from typing import List, Dict, Any, Optional
from enum import Enum

from src.shared.logger import get_logger

logger = get_logger(__name__)


class CategoryType(Enum):
    """Category type enumeration."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    CUSTOM = "custom"


class CategoryManager:
    """Manages category sets and versions."""
    
    def __init__(self):
        self.category_sets = {}  # In-memory storage for now
    
    def create_category_set(self, name: str, categories: List[Dict[str, Any]], 
                          user_id: str, description: str = None) -> Dict[str, Any]:
        """Create a new category set version."""
        try:
            category_set_id = str(uuid.uuid4())
            
            # Validate categories
            validation_result = self._validate_categories(categories)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            # Create category set
            category_set = {
                'id': category_set_id,
                'name': name,
                'description': description or '',
                'categories': categories,
                'created_by': user_id,
                'created_at': self._get_timestamp(),
                'version': 1,
                'parent_version_id': None,
                'is_active': True
            }
            
            self.category_sets[category_set_id] = category_set
            
            logger.info("Category set created", 
                       category_set_id=category_set_id,
                       name=name,
                       category_count=len(categories))
            
            return {
                'success': True,
                'category_set_id': category_set_id,
                'category_set': category_set
            }
            
        except Exception as e:
            logger.error("Failed to create category set", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_category_set_version(self, parent_id: str, updates: Dict[str, Any], 
                                  user_id: str) -> Dict[str, Any]:
        """Create a new version of an existing category set."""
        try:
            if parent_id not in self.category_sets:
                return {
                    'success': False,
                    'error': 'Parent category set not found'
                }
            
            parent_set = self.category_sets[parent_id]
            new_version_id = str(uuid.uuid4())
            
            # Merge updates with parent data
            new_categories = updates.get('categories', parent_set['categories'])
            
            # Validate updated categories
            validation_result = self._validate_categories(new_categories)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            # Create new version
            new_version = {
                'id': new_version_id,
                'name': updates.get('name', parent_set['name']),
                'description': updates.get('description', parent_set['description']),
                'categories': new_categories,
                'created_by': user_id,
                'created_at': self._get_timestamp(),
                'version': parent_set['version'] + 1,
                'parent_version_id': parent_id,
                'is_active': True
            }
            
            # Deactivate parent
            parent_set['is_active'] = False
            
            self.category_sets[new_version_id] = new_version
            
            logger.info("Category set version created", 
                       new_version_id=new_version_id,
                       parent_version_id=parent_id,
                       version=new_version['version'])
            
            return {
                'success': True,
                'category_set_id': new_version_id,
                'category_set': new_version
            }
            
        except Exception as e:
            logger.error("Failed to create category set version", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_category_set(self, category_set_id: str) -> Optional[Dict[str, Any]]:
        """Get category set by ID."""
        return self.category_sets.get(category_set_id)
    
    def get_active_category_sets(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active category sets for a user."""
        return [
            cs for cs in self.category_sets.values()
            if cs['created_by'] == user_id and cs['is_active']
        ]
    
    def _validate_categories(self, categories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate category structure."""
        if not categories:
            return {'valid': False, 'error': 'At least one category is required'}
        
        required_fields = ['id', 'name', 'type']
        
        for i, category in enumerate(categories):
            # Check required fields
            for field in required_fields:
                if field not in category:
                    return {
                        'valid': False, 
                        'error': f'Category {i+1} missing required field: {field}'
                    }
            
            # Validate category ID is UUID
            try:
                uuid.UUID(category['id'])
            except ValueError:
                return {
                    'valid': False,
                    'error': f'Category {i+1} has invalid UUID: {category["id"]}'
                }
            
            # Validate category type
            if category['type'] not in [t.value for t in CategoryType]:
                return {
                    'valid': False,
                    'error': f'Category {i+1} has invalid type: {category["type"]}'
                }
            
            # Validate position is integer
            if 'position' in category:
                if not isinstance(category['position'], int):
                    return {
                        'valid': False,
                        'error': f'Category {i+1} position must be integer'
                    }
            else:
                category['position'] = i  # Default position
        
        # Check for duplicate IDs
        category_ids = [cat['id'] for cat in categories]
        if len(category_ids) != len(set(category_ids)):
            return {
                'valid': False,
                'error': 'Duplicate category IDs found'
            }
        
        return {'valid': True}
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def get_category_display_order(self, category_set_id: str) -> List[Dict[str, Any]]:
        """Get categories sorted by display position."""
        category_set = self.get_category_set(category_set_id)
        if not category_set:
            return []
        
        # Sort by position field
        sorted_categories = sorted(
            category_set['categories'],
            key=lambda x: x.get('position', 0)
        )
        
        return sorted_categories


# Global category manager instance
category_manager = CategoryManager()
