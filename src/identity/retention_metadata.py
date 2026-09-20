"""Retention metadata tracking for data expiration."""
import time
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime, timedelta

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__)


class DataType(Enum):
    SOURCE = "source"
    SNAPSHOT = "snapshot"
    REVIEW_RECORD = "review_record"
    EXPERIMENT_RUN = "experiment_run"
    CLASSIFICATION_RESULT = "classification_result"
    RECOMMENDATION = "recommendation"
    FULL_JOB = "full_job"
    EXPORT = "export"


class RetentionMetadata:
    """Tracks retention metadata for data expiration."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def get_retention_period(self, data_type: DataType, is_anonymous: bool) -> int:
        """Get retention period in seconds based on data type and ownership."""
        if is_anonymous:
            return self.settings.anonymous_data_retention  # 24 hours
        else:
            return self.settings.signed_in_project_retention  # 7 days
    
    def calculate_expiration_time(self, created_at: datetime, is_anonymous: bool) -> datetime:
        """Calculate when data should expire."""
        retention_seconds = self.get_retention_period(DataType.SOURCE, is_anonymous)
        return created_at + timedelta(seconds=retention_seconds)
    
    def is_expired(self, created_at: datetime, is_anonymous: bool) -> bool:
        """Check if data has expired."""
        expiration_time = self.calculate_expiration_time(created_at, is_anonymous)
        return datetime.now() > expiration_time
    
    def get_time_until_expiration(self, created_at: datetime, is_anonymous: bool) -> int:
        """Get seconds until data expires."""
        expiration_time = self.calculate_expiration_time(created_at, is_anonymous)
        remaining = expiration_time - datetime.now()
        return max(0, int(remaining.total_seconds()))
    
    def create_retention_record(self, entity_id: str, entity_type: DataType, 
                              created_at: datetime, is_anonymous: bool) -> Dict[str, Any]:
        """Create retention metadata record."""
        retention_seconds = self.get_retention_period(entity_type, is_anonymous)
        expiration_time = self.calculate_expiration_time(created_at, is_anonymous)
        
        return {
            'entity_id': entity_id,
            'entity_type': entity_type.value,
            'created_at': created_at.isoformat(),
            'retention_seconds': retention_seconds,
            'expiration_time': expiration_time.isoformat(),
            'is_anonymous': is_anonymous,
            'is_expired': self.is_expired(created_at, is_anonymous),
            'time_until_expiration': self.get_time_until_expiration(created_at, is_anonymous)
        }
    
    def get_expiration_display(self, created_at: datetime, is_anonymous: bool) -> str:
        """Get human-readable expiration display."""
        seconds_remaining = self.get_time_until_expiration(created_at, is_anonymous)
        
        if seconds_remaining <= 0:
            return "Expired"
        
        hours = seconds_remaining // 3600
        minutes = (seconds_remaining % 3600) // 60
        
        if hours > 24:
            days = hours // 24
            return f"{days} day{'s' if days != 1 else ''} remaining"
        elif hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''} remaining"
        else:
            return f"{minutes} minute{'s' if minutes != 1 else ''} remaining"
    
    def get_deletion_candidates(self, entity_type: DataType, 
                               created_before: Optional[datetime] = None) -> Dict[str, Any]:
        """Get entities that are candidates for deletion."""
        cutoff_time = created_before or datetime.now()
        
        return {
            'entity_type': entity_type.value,
            'cutoff_time': cutoff_time.isoformat(),
            'anonymous_cutoff': self.calculate_expiration_time(
                cutoff_time - timedelta(seconds=self.settings.anonymous_data_retention), 
                True
            ).isoformat(),
            'signed_in_cutoff': self.calculate_expiration_time(
                cutoff_time - timedelta(seconds=self.settings.signed_in_project_retention), 
                False
            ).isoformat()
        }
    
    def schedule_deletion(self, entity_id: str, entity_type: DataType, 
                         scheduled_time: datetime) -> Dict[str, Any]:
        """Schedule deletion for an entity."""
        return {
            'entity_id': entity_id,
            'entity_type': entity_type.value,
            'scheduled_time': scheduled_time.isoformat(),
            'deletion_type': 'scheduled',
            'created_at': datetime.now().isoformat()
        }
    
    def mark_for_immediate_deletion(self, entity_id: str, entity_type: DataType) -> Dict[str, Any]:
        """Mark entity for immediate deletion."""
        return {
            'entity_id': entity_id,
            'entity_type': entity_type.value,
            'scheduled_time': datetime.now().isoformat(),
            'deletion_type': 'immediate',
            'created_at': datetime.now().isoformat()
        }


# Global retention metadata instance
retention_metadata = RetentionMetadata()
