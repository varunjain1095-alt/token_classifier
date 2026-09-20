"""Ownership scoping for data operations."""
from typing import Optional, List, Dict, Any
from enum import Enum

from src.shared.logger import get_logger
from src.identity.session_manager import session_manager, SessionData, SessionType

logger = get_logger(__name__)


class OwnershipType(Enum):
    ANONYMOUS_SESSION = "anonymous_session"
    SIGNED_IN_USER = "signed_in_user"
    PROJECT = "project"


class OwnershipManager:
    """Manages ownership scoping for all data operations."""
    
    def get_ownership_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get ownership context for a session."""
        session_data = session_manager.get_session(session_id)
        if not session_data:
            return None
        
        if session_data.session_type == SessionType.ANONYMOUS:
            return {
                'type': OwnershipType.ANONYMOUS_SESSION,
                'session_id': session_id,
                'user_id': None,
                'project_id': None,
                'is_anonymous': True
            }
        else:
            return {
                'type': OwnershipType.SIGNED_IN_USER,
                'session_id': session_id,
                'user_id': session_data.user_id,
                'project_id': session_data.project_id,
                'is_anonymous': False
            }
    
    def can_access_entity(self, session_id: str, entity_owner_id: str, 
                         entity_owner_type: OwnershipType) -> bool:
        """Check if session can access an entity."""
        ownership_context = self.get_ownership_context(session_id)
        if not ownership_context:
            return False
        
        # Anonymous sessions can only access their own anonymous data
        if ownership_context['type'] == OwnershipType.ANONYMOUS_SESSION:
            return (entity_owner_type == OwnershipType.ANONYMOUS_SESSION and 
                   entity_owner_id == session_id)
        
        # Signed-in users can access their own data and project data
        if ownership_context['type'] == OwnershipType.SIGNED_IN_USER:
            # Check if it's the user's own data
            if (entity_owner_type == OwnershipType.SIGNED_IN_USER and 
                entity_owner_id == ownership_context['user_id']):
                return True
            
            # Check if it's project data
            if (entity_owner_type == OwnershipType.PROJECT and 
                entity_owner_id == ownership_context['project_id']):
                return True
        
        return False
    
    def get_ownership_filter(self, session_id: str) -> Dict[str, Any]:
        """Get ownership filter for database queries."""
        ownership_context = self.get_ownership_context(session_id)
        if not ownership_context:
            return {'user_id': None, 'project_id': None, 'session_id': None}
        
        if ownership_context['type'] == OwnershipType.ANONYMOUS_SESSION:
            return {
                'session_id': session_id,
                'user_id': None,
                'project_id': None,
                'is_anonymous': True
            }
        else:
            return {
                'session_id': session_id,
                'user_id': ownership_context['user_id'],
                'project_id': ownership_context['project_id'],
                'is_anonymous': False
            }
    
    def validate_entity_creation(self, session_id: str, entity_data: Dict[str, Any]) -> bool:
        """Validate entity creation with proper ownership."""
        ownership_context = self.get_ownership_context(session_id)
        if not ownership_context:
            return False
        
        # Set ownership fields based on session type
        if ownership_context['type'] == OwnershipType.ANONYMOUS_SESSION:
            entity_data['session_id'] = session_id
            entity_data['user_id'] = None
            entity_data['project_id'] = None
            entity_data['is_anonymous'] = True
        else:
            entity_data['session_id'] = session_id
            entity_data['user_id'] = ownership_context['user_id']
            entity_data['project_id'] = ownership_context['project_id']
            entity_data['is_anonymous'] = False
        
        return True
    
    def get_accessible_entities(self, session_id: str, entity_type: str, 
                               entity_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter entities based on ownership access."""
        ownership_context = self.get_ownership_context(session_id)
        if not ownership_context:
            return []
        
        accessible_entities = []
        
        for entity in entity_list:
            entity_owner_id = self._get_entity_owner_id(entity, entity_type)
            entity_owner_type = self._get_entity_owner_type(entity, entity_type)
            
            if self.can_access_entity(session_id, entity_owner_id, entity_owner_type):
                accessible_entities.append(entity)
        
        return accessible_entities
    
    def _get_entity_owner_id(self, entity: Dict[str, Any], entity_type: str) -> str:
        """Get owner ID from entity based on type."""
        if entity_type == 'source':
            return entity.get('created_by', '')
        elif entity_type == 'snapshot':
            return entity.get('source_id', '')
        elif entity_type == 'review_record':
            return entity.get('snapshot_id', '')
        elif entity_type == 'workload_version':
            return entity.get('snapshot_id', '')
        else:
            return entity.get('id', '')
    
    def _get_entity_owner_type(self, entity: Dict[str, Any], entity_type: str) -> OwnershipType:
        """Get owner type from entity based on type."""
        if entity.get('is_anonymous', False):
            return OwnershipType.ANONYMOUS_SESSION
        elif entity.get('user_id'):
            return OwnershipType.SIGNED_IN_USER
        elif entity.get('project_id'):
            return OwnershipType.PROJECT
        else:
            return OwnershipType.ANONYMOUS_SESSION
    
    def validate_ownership_transition(self, session_id: str, from_entity: Dict[str, Any], 
                                    to_entity: Dict[str, Any]) -> bool:
        """Validate ownership transition between entities."""
        # Ensure the new entity inherits proper ownership
        ownership_context = self.get_ownership_context(session_id)
        if not ownership_context:
            return False
        
        # Copy ownership fields from parent to child
        ownership_fields = ['session_id', 'user_id', 'project_id', 'is_anonymous']
        for field in ownership_fields:
            if field in from_entity:
                to_entity[field] = from_entity[field]
        
        return True
    
    def get_ownership_display(self, entity: Dict[str, Any]) -> str:
        """Get human-readable ownership display."""
        if entity.get('is_anonymous', False):
            return "Anonymous Session"
        elif entity.get('user_id'):
            return f"User: {entity['user_id'][:8]}..."
        elif entity.get('project_id'):
            return f"Project: {entity['project_id'][:8]}..."
        else:
            return "Unknown"


# Global ownership manager instance
ownership_manager = OwnershipManager()
