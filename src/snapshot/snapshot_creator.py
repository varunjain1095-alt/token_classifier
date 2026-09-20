"""Snapshot creation for dataset snapshots and review records."""
import uuid
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.shared.logger import get_logger
from src.identity.ownership import ownership_manager
from src.identity.retention_metadata import retention_metadata, DataType
from src.models.source import Source, DatasetSnapshot, ReviewRecord
from src.intake.db_extractor import db_extractor
from src.intake.db_adapters.base import FilterCondition

logger = get_logger(__name__)


class SnapshotCreator:
    """Creates dataset snapshots and review records."""
    
    def __init__(self):
        pass
    
    def create_file_snapshot(self, source_data: Dict[str, Any], 
                           parse_result: Dict[str, Any],
                           session_id: str) -> Dict[str, Any]:
        """Create snapshot from file upload."""
        try:
            # Create snapshot record
            snapshot_id = str(uuid.uuid4())
            snapshot_data = {
                'id': snapshot_id,
                'source_id': source_data['id'],
                'extraction_start_time': datetime.now(),
                'extraction_end_time': datetime.now(),
                'mapping': json.dumps({'file_type': parse_result['file_type']}),
                'selection_filter_specification': json.dumps({}),
                'exact_captured_count': parse_result['total_rows'],
                'eligibility_counts': json.dumps({
                    'total': parse_result['total_rows'],
                    'eligible': parse_result['total_rows'],  # All rows eligible initially
                    'excluded': 0
                }),
                'content_hash': self._calculate_content_hash(parse_result),
                'consistency_mode': 'file_upload'
            }
            
            # Set ownership
            ownership_manager.validate_entity_creation(session_id, snapshot_data)
            
            # Create review records
            review_records = self._create_review_records(
                snapshot_id, 
                parse_result['preview_rows'], 
                parse_result['headers'],
                session_id
            )
            
            logger.info("File snapshot created", 
                       snapshot_id=snapshot_id,
                       source_id=source_data['id'],
                       record_count=len(review_records))
            
            return {
                'snapshot_id': snapshot_id,
                'snapshot_data': snapshot_data,
                'review_records': review_records,
                'record_count': len(review_records)
            }
            
        except Exception as e:
            logger.error("File snapshot creation failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_database_snapshot(self, adapter_type: str, connection_params: Dict[str, Any],
                               schema: str, table_name: str, columns: List[str],
                               filters: List[FilterCondition], session_id: str) -> Dict[str, Any]:
        """Create snapshot from database extraction."""
        try:
            # Extract data from database
            extraction_result = db_extractor.extract_data(
                adapter_type, connection_params, schema, table_name,
                columns, filters
            )
            
            if not extraction_result['success']:
                return {
                    'success': False,
                    'error': extraction_result['error']
                }
            
            # Create source record for database
            source_id = str(uuid.uuid4())
            source_data = {
                'id': source_id,
                'type': 'database',
                'display_name': f"{schema}.{table_name}",
                'format_adapter': adapter_type,
                'connection_reference': f"{connection_params.get('host')}:{connection_params.get('port')}",
                'created_by': session_id
            }
            
            # Set ownership
            ownership_manager.validate_entity_creation(session_id, source_data)
            
            # Create snapshot record
            snapshot_id = str(uuid.uuid4())
            snapshot_data = {
                'id': snapshot_id,
                'source_id': source_id,
                'extraction_start_time': datetime.now(),
                'extraction_end_time': datetime.now(),
                'mapping': json.dumps({
                    'adapter': adapter_type,
                    'schema': schema,
                    'table': table_name,
                    'columns': columns
                }),
                'selection_filter_specification': json.dumps([f.__dict__ for f in filters]),
                'exact_captured_count': extraction_result['total_extracted'],
                'eligibility_counts': json.dumps({
                    'total': extraction_result['total_extracted'],
                    'eligible': extraction_result['total_extracted'],
                    'excluded': 0
                }),
                'content_hash': self._calculate_content_hash(extraction_result),
                'consistency_mode': extraction_result.get('extraction_method', 'unknown')
            }
            
            # Set ownership
            ownership_manager.validate_entity_creation(session_id, snapshot_data)
            
            # Create review records
            review_records = self._create_review_records(
                snapshot_id,
                extraction_result['rows'],
                extraction_result['columns'],
                session_id
            )
            
            logger.info("Database snapshot created", 
                       snapshot_id=snapshot_id,
                       source_id=source_id,
                       table=f"{schema}.{table_name}",
                       record_count=len(review_records))
            
            return {
                'success': True,
                'snapshot_id': snapshot_id,
                'source_data': source_data,
                'snapshot_data': snapshot_data,
                'review_records': review_records,
                'record_count': len(review_records),
                'extraction_result': extraction_result
            }
            
        except Exception as e:
            logger.error("Database snapshot creation failed", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_review_records(self, snapshot_id: str, rows: List[List[Any]], 
                              columns: List[str], session_id: str) -> List[Dict[str, Any]]:
        """Create review record entities."""
        review_records = []
        
        for i, row in enumerate(rows):
            record_id = str(uuid.uuid4())
            
            # Create mapped metadata
            mapped_metadata = {}
            for j, column_name in enumerate(columns):
                if j < len(row):
                    mapped_metadata[column_name] = row[j]
            
            # Extract review text (assume first text column or first column)
            review_text = self._extract_review_text(row, columns, mapped_metadata)
            
            # Create review record
            record_data = {
                'id': record_id,
                'snapshot_id': snapshot_id,
                'original_source_id': f"row_{i}",
                'original_review_text': review_text,
                'mapped_metadata': json.dumps(mapped_metadata),
                'source_row_locator': f"row_{i}",
                'content_hash': self._calculate_row_hash(row),
                'eligibility_reason': None  # All records initially eligible
            }
            
            # Set ownership
            ownership_manager.validate_entity_creation(session_id, record_data)
            
            review_records.append(record_data)
        
        return review_records
    
    def _extract_review_text(self, row: List[Any], columns: List[str], 
                            mapped_metadata: Dict[str, Any]) -> str:
        """Extract review text from row data."""
        # Look for text-like columns
        text_columns = ['text', 'review', 'comment', 'content', 'description', 'body']
        
        # First, try to find a column with text-like name
        for i, column_name in enumerate(columns):
            if any(text_col in column_name.lower() for text_col in text_columns):
                if i < len(row) and row[i] is not None:
                    return str(row[i])
        
        # If no text-like column found, use first non-empty string column
        for i, value in enumerate(row):
            if value is not None and isinstance(value, str) and len(str(value)) > 10:
                return str(value)
        
        # Fallback to first column
        if row and row[0] is not None:
            return str(row[0])
        
        return ""
    
    def _calculate_content_hash(self, data: Dict[str, Any]) -> str:
        """Calculate content hash for snapshot."""
        content_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _calculate_row_hash(self, row: List[Any]) -> str:
        """Calculate content hash for a row."""
        row_str = json.dumps(row, sort_keys=True, default=str)
        return hashlib.sha256(row_str.encode()).hexdigest()


# Global snapshot creator instance
snapshot_creator = SnapshotCreator()
