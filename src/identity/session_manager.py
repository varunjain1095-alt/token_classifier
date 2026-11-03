"""Session management for anonymous and signed-in users."""
import json
import secrets
import time
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__)


class SessionType(Enum):
    ANONYMOUS = "anonymous"
    SIGNED_IN = "signed_in"


class SessionData(BaseModel):
    """Session data stored in Redis."""
    session_id: str
    session_type: SessionType
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: float
    last_activity: float
    ip_address: str
    user_agent: str
    free_preview_used: bool = False
    rate_limit_count: int = 0
    rate_limit_reset_time: float = 0
    project_state: Optional[Dict[str, Any]] = None


class SessionManager:
    """Manages anonymous and signed-in sessions with server-side enforcement."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Try to connect to Redis, fallback to in-memory if not available
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(self.settings.redis_url)
                self.redis_client.ping()  # Test connection
                self.use_redis = True
                logger.info("Connected to Redis for session management")
            except Exception as e:
                logger.warning("Redis not available, using in-memory sessions", error=str(e))
                self.redis_client = None
                self.use_redis = False
        else:
            self.redis_client = None
            self.use_redis = False
        
        # In-memory fallback
        self.memory_sessions = {}
        self.session_timeout = self.settings.session_timeout
        self.permanent_session_lifetime = self.settings.permanent_session_lifetime
        self.storage_dir = Path('tmp/sessions')

    def _persist(self, session_data: SessionData) -> None:
        """Write a session to disk so a backend restart does not log the
        user out or lose their wizard progress. Only used in the in-memory
        fallback mode — Redis handles durability itself."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            (self.storage_dir / f"{session_data.session_id}.json").write_text(
                session_data.json(), encoding='utf-8')
        except Exception as e:
            logger.warning("Failed to persist session",
                           session_id=session_data.session_id, error=str(e))

    def _load_from_disk(self, session_id: str) -> Optional[SessionData]:
        """Restore a session checkpoint written by _persist."""
        path = self.storage_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            session_data = SessionData.parse_raw(path.read_text(encoding='utf-8'))
            self.memory_sessions[session_id] = session_data
            logger.info("Session restored from disk", session_id=session_id)
            return session_data
        except Exception as e:
            logger.warning("Failed to load session checkpoint",
                           session_id=session_id, error=str(e))
            return None
    
    def create_anonymous_session(self, request: Request) -> str:
        """Create a new anonymous session."""
        session_id = secrets.token_urlsafe(32)
        session_data = SessionData(
            session_id=session_id,
            session_type=SessionType.ANONYMOUS,
            created_at=time.time(),
            last_activity=time.time(),
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown")
        )
        
        if self.use_redis:
            # Store in Redis
            self.redis_client.setex(
                f"session:{session_id}",
                self.permanent_session_lifetime,
                session_data.json()
            )
        else:
            # Store in memory
            self.memory_sessions[session_id] = session_data
            self._persist(session_data)

        logger.info("Anonymous session created", session_id=session_id)
        return session_id
    
    def validate_session(self, session_id: str, request: Request) -> Optional[SessionData]:
        """Validate session and return session data."""
        if not session_id:
            return None
        
        session_data = None
        
        if self.use_redis:
            # Get from Redis
            session_json = self.redis_client.get(f"session:{session_id}")
            if session_json:
                session_data = SessionData.parse_raw(session_json)
        else:
            # Get from memory, restoring the on-disk checkpoint after a restart
            session_data = (self.memory_sessions.get(session_id)
                            or self._load_from_disk(session_id))

        if not session_data:
            return None
        
        # Check if session expired
        if time.time() - session_data.last_activity > self.session_timeout:
            self.delete_session(session_id)
            return None
        
        # Update last activity
        session_data.last_activity = time.time()
        
        if self.use_redis:
            self.redis_client.setex(
                f"session:{session_id}",
                self.permanent_session_lifetime,
                session_data.json()
            )
        else:
            self.memory_sessions[session_id] = session_data
        
        return session_data
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data by ID (alias for validate_session)."""
        return self.validate_session(session_id, None)

    def update_project_state(self, session_id: str, project_state: Dict[str, Any]) -> bool:
        """Persist wizard/project state on the session so it survives page refresh."""
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        session_data.project_state = project_state
        if self.use_redis:
            self.redis_client.setex(
                f"session:{session_id}",
                self.permanent_session_lifetime,
                session_data.json()
            )
        else:
            self.memory_sessions[session_id] = session_data
            self._persist(session_data)
        return True

    def delete_session(self, session_id: str):
        """Delete session."""
        if self.use_redis:
            self.redis_client.delete(f"session:{session_id}")
        else:
            self.memory_sessions.pop(session_id, None)
            (self.storage_dir / f"{session_id}.json").unlink(missing_ok=True)

        logger.info("Session deleted", session_id=session_id)
    
    def get_session_count(self) -> int:
        """Get total session count."""
        if self.use_redis:
            return len(self.redis_client.keys("session:*"))
        else:
            return len(self.memory_sessions)


# Global session manager instance
session_manager = SessionManager()
