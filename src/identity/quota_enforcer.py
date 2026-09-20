"""Quota enforcement for preview limits, rate limits, and spend limits."""
import time
from typing import Optional, Dict, Any
from enum import Enum

from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.identity.session_manager import session_manager, SessionData, SessionType

logger = get_logger(__name__)


class QuotaType(Enum):
    FREE_PREVIEW = "free_preview"
    RATE_LIMIT = "rate_limit"
    SPEND_LIMIT = "spend_limit"
    CONCURRENT_CALLS = "concurrent_calls"


class QuotaEnforcer:
    """Enforces quotas and limits server-side."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def check_free_preview_quota(self, session_id: str) -> bool:
        """Check if anonymous session can use free preview."""
        session_data = session_manager.get_session(session_id)
        if not session_data:
            return False
        
        if session_data.session_type != SessionType.ANONYMOUS:
            return True  # Signed-in users don't have free preview limits
        
        # Check if free preview already used
        if session_data.free_preview_used:
            logger.warning("Free preview already used", session_id=session_id[:8])
            return False
        
        # Check if global free preview budget is available
        if not self._check_global_free_budget():
            logger.warning("Global free preview budget exhausted", session_id=session_id[:8])
            return False
        
        return True
    
    def use_free_preview_quota(self, session_id: str) -> bool:
        """Use free preview quota for anonymous session."""
        if not self.check_free_preview_quota(session_id):
            return False
        
        # Mark free preview as used
        if not session_manager.use_free_preview(session_id):
            return False
        
        # Decrement global budget
        self._decrement_global_free_budget()
        
        logger.info("Free preview quota used", session_id=session_id[:8])
        return True
    
    def check_rate_limit(self, session_id: str) -> bool:
        """Check if session has exceeded rate limits."""
        return session_manager.check_rate_limit(session_id)
    
    def check_spend_limit(self, session_id: str, estimated_cost: float) -> bool:
        """Check if session would exceed spend limits."""
        session_data = session_manager.get_session(session_id)
        if not session_data:
            return False
        
        # Get current spend for this session
        current_spend = self._get_session_spend(session_id)
        
        # Check if adding estimated cost would exceed limit
        max_spend = self._get_session_spend_limit(session_data.session_type)
        
        if current_spend + estimated_cost > max_spend:
            logger.warning("Spend limit would be exceeded", 
                         session_id=session_id[:8],
                         current_spend=current_spend,
                         estimated_cost=estimated_cost,
                         max_spend=max_spend)
            return False
        
        return True
    
    def check_concurrent_calls_limit(self, session_id: str) -> bool:
        """Check if session has too many concurrent calls."""
        # Get current concurrent calls for this session
        concurrent_calls = self._get_concurrent_calls(session_id)
        max_concurrent = self._get_concurrent_calls_limit()
        
        if concurrent_calls >= max_concurrent:
            logger.warning("Concurrent calls limit exceeded", 
                         session_id=session_id[:8],
                         concurrent_calls=concurrent_calls,
                         max_concurrent=max_concurrent)
            return False
        
        return True
    
    def increment_concurrent_calls(self, session_id: str) -> bool:
        """Increment concurrent calls counter."""
        if not self.check_concurrent_calls_limit(session_id):
            return False
        
        current_calls = self._get_concurrent_calls(session_id)
        self._set_concurrent_calls(session_id, current_calls + 1)
        return True
    
    def decrement_concurrent_calls(self, session_id: str) -> bool:
        """Decrement concurrent calls counter."""
        current_calls = self._get_concurrent_calls(session_id)
        if current_calls > 0:
            self._set_concurrent_calls(session_id, current_calls - 1)
        return True
    
    def record_spend(self, session_id: str, actual_cost: float) -> bool:
        """Record actual spend for a session."""
        current_spend = self._get_session_spend(session_id)
        new_spend = current_spend + actual_cost
        
        # Store updated spend (in production, use Redis with TTL)
        if not hasattr(self, '_session_spend'):
            self._session_spend = {}
        
        self._session_spend[session_id] = {
            'total_spend': new_spend,
            'last_updated': time.time()
        }
        
        logger.info("Spend recorded", 
                   session_id=session_id[:8],
                   actual_cost=actual_cost,
                   total_spend=new_spend)
        return True
    
    def _check_global_free_budget(self) -> bool:
        """Check if global free preview budget is available."""
        # In production, this would check a global counter in Redis
        # For now, assume budget is available
        return True
    
    def _decrement_global_free_budget(self) -> bool:
        """Decrement global free preview budget."""
        # In production, this would decrement a global counter in Redis
        # For now, assume success
        return True
    
    def _get_session_spend(self, session_id: str) -> float:
        """Get current spend for a session."""
        if not hasattr(self, '_session_spend') or session_id not in self._session_spend:
            return 0.0
        
        spend_data = self._session_spend[session_id]
        
        # Check if spend data is expired (reset daily)
        if time.time() - spend_data['last_updated'] > 86400:  # 24 hours
            return 0.0
        
        return spend_data['total_spend']
    
    def _get_session_spend_limit(self, session_type: SessionType) -> float:
        """Get spend limit based on session type."""
        if session_type == SessionType.ANONYMOUS:
            return 0.10  # $0.10 limit for anonymous users
        else:
            return 10.00  # $10.00 limit for signed-in users
    
    def _get_concurrent_calls(self, session_id: str) -> int:
        """Get current concurrent calls for a session."""
        if not hasattr(self, '_concurrent_calls') or session_id not in self._concurrent_calls:
            return 0
        
        calls_data = self._concurrent_calls[session_id]
        
        # Check if calls data is expired (reset after 1 minute)
        if time.time() - calls_data['last_updated'] > 60:
            return 0
        
        return calls_data['count']
    
    def _set_concurrent_calls(self, session_id: str, count: int) -> bool:
        """Set concurrent calls count for a session."""
        if not hasattr(self, '_concurrent_calls'):
            self._concurrent_calls = {}
        
        self._concurrent_calls[session_id] = {
            'count': count,
            'last_updated': time.time()
        }
        return True
    
    def _get_concurrent_calls_limit(self) -> int:
        """Get maximum concurrent calls limit."""
        return 5  # Maximum 5 concurrent calls per session
    
    def validate_request(self, session_id: str, request_type: str, estimated_cost: float = 0.0) -> bool:
        """Validate a request against all applicable quotas."""
        # Check rate limit first
        if not self.check_rate_limit(session_id):
            logger.warning("Rate limit exceeded", session_id=session_id[:8])
            return False
        
        # Check concurrent calls limit
        if not self.check_concurrent_calls_limit(session_id):
            return False
        
        # Check spend limit if cost is involved
        if estimated_cost > 0 and not self.check_spend_limit(session_id, estimated_cost):
            return False
        
        # Check specific quotas based on request type
        if request_type == "preview" and session_manager.get_session(session_id).session_type == SessionType.ANONYMOUS:
            if not self.check_free_preview_quota(session_id):
                return False
        
        return True


# Global quota enforcer instance
quota_enforcer = QuotaEnforcer()
