"""Bounded preview generation from database."""
from typing import List, Dict, Any, Optional
from src.shared.logger import get_logger
from .db_adapters.base import DatabaseAdapterFactory, FilterCondition, QueryResult

logger = get_logger(__name__)


class DatabasePreview:
    """Generates bounded preview data from database."""
    
    def __init__(self):
        self.factory = DatabaseAdapterFactory()
        self.default_preview_limit = 100
        self.max_preview_limit = 1000
    
    def get_preview(self, adapter_type: str, connection_params: Dict[str, Any],
                   schema: str, table_name: str, columns: List[str],
                   filters: List[FilterCondition], limit: int = 100) -> Dict[str, Any]:
        """Get bounded preview data."""
        try:
            # Validate limit
            if limit > self.max_preview_limit:
                limit = self.max_preview_limit
                logger.warning("Preview limit capped", 
                             requested_limit=limit,
                             max_limit=self.max_preview_limit)
            
            # Create adapter
            adapter = self.factory.create_adapter(adapter_type)
            
            # Get preview data
            result = adapter.get_preview_data(
                connection_params, schema, table_name,
                columns, filters, limit, 0
            )
            
            # Get row count
            count_result = adapter.get_row_count(
                connection_params, schema, table_name, filters
            )
            
            # Format preview data
            preview_data = {
                'success': True,
                'schema': schema,
                'table_name': table_name,
                'columns': result.columns,
                'rows': result.rows,
                'preview_count': result.row_count,
                'total_count': count_result.get('count', 0),
                'count_status': count_result.get('status', 'unknown'),
                'count_method': count_result.get('method', 'unknown'),
                'has_more': result.has_more,
                'limit': limit,
                'filters_applied': len(filters),
                'adapter': adapter_type
            }
            
            logger.info("Preview generated", 
                       schema=schema,
                       table_name=table_name,
                       preview_count=result.row_count,
                       total_count=count_result.get('count'))
            
            return preview_data
            
        except Exception as e:
            logger.error("Preview generation failed", 
                        adapter=adapter_type,
                        schema=schema,
                        table_name=table_name,
                        error=str(e))
            
            return {
                'success': False,
                'error': str(e),
                'schema': schema,
                'table_name': table_name
            }
    
    def get_column_preview(self, adapter_type: str, connection_params: Dict[str, Any],
                          schema: str, table_name: str, column_name: str,
                          limit: int = 50) -> Dict[str, Any]:
        """Get preview of a single column."""
        try:
            adapter = self.factory.create_adapter(adapter_type)
            
            # Get preview data for single column
            result = adapter.get_preview_data(
                connection_params, schema, table_name,
                [column_name], [], limit, 0
            )
            
            # Extract unique values
            unique_values = list(set(row[0] for row in result.rows if row[0] is not None))
            unique_values.sort()
            
            return {
                'success': True,
                'column_name': column_name,
                'unique_values': unique_values[:limit],
                'total_unique': len(unique_values),
                'sample_values': result.rows[:10],
                'adapter': adapter_type
            }
            
        except Exception as e:
            logger.error("Column preview failed", 
                        adapter=adapter_type,
                        schema=schema,
                        table_name=table_name,
                        column_name=column_name,
                        error=str(e))
            
            return {
                'success': False,
                'error': str(e),
                'column_name': column_name
            }
    
    def get_sample_values(self, adapter_type: str, connection_params: Dict[str, Any],
                         schema: str, table_name: str, column_name: str,
                         sample_size: int = 10) -> Dict[str, Any]:
        """Get sample values from a column."""
        try:
            adapter = self.factory.create_adapter(adapter_type)
            
            # Get random sample
            result = adapter.get_preview_data(
                connection_params, schema, table_name,
                [column_name], [], sample_size, 0
            )
            
            return {
                'success': True,
                'column_name': column_name,
                'sample_values': [row[0] for row in result.rows],
                'sample_size': len(result.rows),
                'adapter': adapter_type
            }
            
        except Exception as e:
            logger.error("Sample values failed", 
                        adapter=adapter_type,
                        schema=schema,
                        table_name=table_name,
                        column_name=column_name,
                        error=str(e))
            
            return {
                'success': False,
                'error': str(e),
                'column_name': column_name
            }


# Global preview generator instance
db_preview = DatabasePreview()
