"""User and project management."""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.identity.session_manager import session_manager, SessionType

logger = get_logger(__name__)


class User:
    """User entity."""
    
    def __init__(self, user_id: str, email: str, created_at: datetime):
        self.user_id = user_id
        self.email = email
        self.created_at = created_at
        self.last_activity = created_at
        self.is_active = True


class Project:
    """Project entity."""
    
    def __init__(self, project_id: str, user_id: str, name: str, created_at: datetime):
        self.project_id = project_id
        self.user_id = user_id
        self.name = name
        self.created_at = created_at
        self.last_activity = created_at
        self.is_active = True


class UserManager:
    """Manages users and projects."""
    
    def __init__(self):
        self.settings = get_settings()
        # In production, this would use a database
        self._users: Dict[str, User] = {}
        self._projects: Dict[str, Project] = {}
    
    def create_user(self, email: str) -> User:
        """Create a new user."""
        user_id = str(uuid.uuid4())
        user = User(user_id, email, datetime.now())
        self._users[user_id] = user
        
        logger.info("User created", user_id=user_id[:8], email=email)
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)
    
    def create_project(self, user_id: str, name: str) -> Project:
        """Create a new project for a user."""
        project_id = str(uuid.uuid4())
        project = Project(project_id, user_id, name, datetime.now())
        self._projects[project_id] = project
        
        logger.info("Project created", project_id=project_id[:8], user_id=user_id[:8], name=name)
        return project
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID."""
        return self._projects.get(project_id)
    
    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects for a user."""
        return [p for p in self._projects.values() if p.user_id == user_id and p.is_active]
    
    def update_project_activity(self, project_id: str) -> bool:
        """Update project last activity."""
        if project_id in self._projects:
            self._projects[project_id].last_activity = datetime.now()
            return True
        return False
    
    def deactivate_project(self, project_id: str) -> bool:
        """Deactivate a project."""
        if project_id in self._projects:
            self._projects[project_id].is_active = False
            logger.info("Project deactivated", project_id=project_id[:8])
            return True
        return False
    
    def get_project_retention_time(self, project_id: str) -> Optional[datetime]:
        """Get project expiration time based on last activity."""
        project = self.get_project(project_id)
        if not project:
            return None
        
        return project.last_activity + timedelta(seconds=self.settings.signed_in_project_retention)
    
    def is_project_expired(self, project_id: str) -> bool:
        """Check if project has expired."""
        expiration_time = self.get_project_retention_time(project_id)
        if not expiration_time:
            return True
        
        return datetime.now() > expiration_time
    
    def create_signed_in_session(self, user_id: str, project_id: str, request) -> str:
        """Create a signed-in session for a user and project."""
        return session_manager.create_signed_in_session(user_id, project_id, request)
    
    def validate_project_access(self, user_id: str, project_id: str) -> bool:
        """Validate that a user can access a project."""
        project = self.get_project(project_id)
        if not project:
            return False
        
        return project.user_id == user_id and project.is_active and not self.is_project_expired(project_id)
    
    def get_project_display_info(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project display information."""
        project = self.get_project(project_id)
        if not project:
            return None
        
        expiration_time = self.get_project_retention_time(project_id)
        is_expired = self.is_project_expired(project_id)
        
        return {
            'project_id': project_id,
            'name': project.name,
            'created_at': project.created_at.isoformat(),
            'last_activity': project.last_activity.isoformat(),
            'expiration_time': expiration_time.isoformat() if expiration_time else None,
            'is_expired': is_expired,
            'is_active': project.is_active
        }


# Global user manager instance
user_manager = UserManager()
