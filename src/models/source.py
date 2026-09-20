"""Source entity model."""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Source(Base):
    """Source entity representing a data source."""
    
    __tablename__ = 'sources'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), nullable=False)  # 'file', 'database'
    display_name = Column(String(255), nullable=False)
    format_adapter = Column(String(100), nullable=True)
    file_reference = Column(Text, nullable=True)  # File path or connection string
    connection_reference = Column(Text, nullable=True)  # Database connection details
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)  # Session ID or user ID
    
    # Relationships
    snapshots = relationship("DatasetSnapshot", back_populates="source")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'type': self.type,
            'display_name': self.display_name,
            'format_adapter': self.format_adapter,
            'file_reference': self.file_reference,
            'connection_reference': self.connection_reference,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Source':
        """Create from dictionary."""
        source = cls()
        source.id = uuid.UUID(data['id']) if data.get('id') else uuid.uuid4()
        source.type = data['type']
        source.display_name = data['display_name']
        source.format_adapter = data.get('format_adapter')
        source.file_reference = data.get('file_reference')
        source.connection_reference = data.get('connection_reference')
        source.created_by = data['created_by']
        return source


class DatasetSnapshot(Base):
    """Dataset snapshot entity."""
    
    __tablename__ = 'dataset_snapshots'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey('sources.id'), nullable=False)
    extraction_start_time = Column(DateTime(timezone=True), nullable=True)
    extraction_end_time = Column(DateTime(timezone=True), nullable=True)
    mapping = Column(Text, nullable=True)  # JSON string of field mapping
    selection_filter_specification = Column(Text, nullable=True)  # JSON string of filters
    exact_captured_count = Column(Integer, nullable=True)
    eligibility_counts = Column(Text, nullable=True)  # JSON string of counts
    content_hash = Column(String(64), nullable=True)
    consistency_mode = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    source = relationship("Source", back_populates="snapshots")
    review_records = relationship("ReviewRecord", back_populates="snapshot")
    workload_versions = relationship("WorkloadVersion", back_populates="snapshot")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'source_id': str(self.source_id),
            'extraction_start_time': self.extraction_start_time.isoformat() if self.extraction_start_time else None,
            'extraction_end_time': self.extraction_end_time.isoformat() if self.extraction_end_time else None,
            'mapping': self.mapping,
            'selection_filter_specification': self.selection_filter_specification,
            'exact_captured_count': self.exact_captured_count,
            'eligibility_counts': self.eligibility_counts,
            'content_hash': self.content_hash,
            'consistency_mode': self.consistency_mode,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ReviewRecord(Base):
    """Review record entity."""
    
    __tablename__ = 'review_records'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey('dataset_snapshots.id'), nullable=False)
    original_source_id = Column(String(255), nullable=True)
    original_review_text = Column(Text, nullable=False)
    mapped_metadata = Column(Text, nullable=True)  # JSON string of mapped metadata
    source_row_locator = Column(String(255), nullable=True)
    content_hash = Column(String(64), nullable=True)
    eligibility_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    snapshot = relationship("DatasetSnapshot", back_populates="review_records")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'snapshot_id': str(self.snapshot_id),
            'original_source_id': self.original_source_id,
            'original_review_text': self.original_review_text,
            'mapped_metadata': self.mapped_metadata,
            'source_row_locator': self.source_row_locator,
            'content_hash': self.content_hash,
            'eligibility_reason': self.eligibility_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WorkloadVersion(Base):
    """Workload version entity."""
    
    __tablename__ = 'workload_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey('dataset_snapshots.id'), nullable=False)
    selection_mode = Column(String(50), nullable=False)
    requested_percentage = Column(Integer, nullable=True)
    requested_count = Column(Integer, nullable=True)
    rounding_rule = Column(String(50), nullable=True)
    seed = Column(Integer, nullable=True)
    ordered_record_ids = Column(Text, nullable=True)  # JSON string of record IDs
    resolved_count = Column(Integer, nullable=True)
    review_text_token_total = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    snapshot = relationship("DatasetSnapshot", back_populates="workload_versions")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'snapshot_id': str(self.snapshot_id),
            'selection_mode': self.selection_mode,
            'requested_percentage': self.requested_percentage,
            'requested_count': self.requested_count,
            'rounding_rule': self.rounding_rule,
            'seed': self.seed,
            'ordered_record_ids': self.ordered_record_ids,
            'resolved_count': self.resolved_count,
            'review_text_token_total': self.review_text_token_total,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WorkloadVersion(Base):
    """Workload version entity."""
    
    __tablename__ = 'workload_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey('dataset_snapshots.id'), nullable=False)
    selection_mode = Column(String(50), nullable=False)
    requested_percentage = Column(Integer, nullable=True)
    requested_count = Column(Integer, nullable=True)
    rounding_rule = Column(String(50), nullable=True)
    seed = Column(Integer, nullable=True)
    ordered_record_ids = Column(Text, nullable=True)  # JSON string of record IDs
    resolved_count = Column(Integer, nullable=True)
    review_text_token_total = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    snapshot = relationship("DatasetSnapshot", back_populates="workload_versions")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'snapshot_id': str(self.snapshot_id),
            'selection_mode': self.selection_mode,
            'requested_percentage': self.requested_percentage,
            'requested_count': self.requested_count,
            'rounding_rule': self.rounding_rule,
            'seed': self.seed,
            'ordered_record_ids': self.ordered_record_ids,
            'resolved_count': self.resolved_count,
            'review_text_token_total': self.review_text_token_total,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
