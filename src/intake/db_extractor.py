"""Database data extraction with pagination."""
from typing import List, Dict, Any, Optional, Tuple
from src.shared.logger import get_logger
from .db_adapters.base import DatabaseAdapterFactory, FilterCondition, QueryResult

logger = get_logger(__name__)


class DatabaseExtractor:
    """Extracts data from database with pagination support."""
    
    def __init__(self):
        self.factory = DatabaseAdapterFactory()
        self.default_batch_size = 1000
        self.max_batch_size = 5000
    
    def extract_data(self, adapter_type: str, connection_params: Dict[str, Any],
                    schema: str, table_name: str, columns: List[str],
                    filters: List[FilterCondition], 
                    max_rows: Optional[int] = None) -> Dict[str, Any]:
        """Extract data with automatic pagination."""
        try:
            # Create adapter
            adapter = self.factory.create_adapter(adapter_type)
            
            # Get stable key columns for pagination
            stable_keys = adapter.get_stable_key_columns(connection_params, schema, table_name)
            stable_key = stable_keys[0] if stable_keys else None
            
            logger.info("Starting data extraction", 
                       schema=schema,
                       table_name=table_name,
                       stable_key=stable_key,
                       max_rows=max_rows)
            
            # Extract data
            all_rows = []
            all_columns = []
            total_extracted = 0
            last_key_value = None
            batch_size = min(self.default_batch_size, max_rows or self.default_batch_size)
            
            while True:
                # Extract batch
                result = adapter.extract_data(
                    connection_params, schema, table_name,
                    columns, filters, stable_key, last_key_value, batch_size
                )
                
                if not result.rows:
                    break
                
                # Store columns from first batch
                if not all_columns:
                    all_columns = result.columns
                
                # Add rows
                all_rows.extend(result.rows)
                total_extracted += result.row_count
                
                # Update pagination
                if stable_key and result.total_count is not None:
                    last_key_value = result.total_count
                else:
                    last_key_value = None
                
                # Check limits
                if max_rows and total_extracted >= max_rows:
                    logger.info("Reached maximum row limit", 
                               extracted=total_extracted,
                               max_rows=max_rows)
                    break
                
                if not result.has_more:
                    break
                
                logger.debug("Extracted batch", 
                           batch_size=result.row_count,
                           total_extracted=total_extracted)
            
            extraction_result = {
                'success': True,
                'schema': schema,
                'table_name': table_name,
                'columns': all_columns,
                'rows': all_rows,
                'total_extracted': total_extracted,
                'stable_key': stable_key,
                'stable_keys_available': len(stable_keys),
                'adapter': adapter_type,
                'extraction_method': 'keyset' if stable_key else 'offset'
            }
            
            logger.info("Data extraction completed", 
                       schema=schema,
                       table_name=table_name,
                       total_extracted=total_extracted,
                       method=extraction_result['extraction_method'])
            
            return extraction_result
            
        except Exception as e:
            logger.error("Data extraction failed", 
                        adapter=adapter_type,
                        schema=schema,
                        table_name=table_name,
                        error=str(e))
            
            return {
                'success': False,
                'error': str(e),
                'schema': schema,
                'table_name': table_name,
                'total_extracted': 0
            }
    
    def estimate_extraction_time(self, adapter_type: str, connection_params: Dict[str, Any],
                               schema: str, table_name: str, 
                               filters: List[FilterCondition]) -> Dict[str, Any]:
        """Estimate extraction time for planning."""
        try:
            adapter = self.factory.create_adapter(adapter_type)
            
            # Get row count
            count_result = adapter.get_row_count(
                connection_params, schema, table_name, filters
            )
            
            # Get stable key availability
            stable_keys = adapter.get_stable_key_columns(connection_params, schema, table_name)
            
            # Estimate based on row count and method
            estimated_rows = count_result.get('count', 0)
            method = 'keyset' if stable_keys else 'offset'
            
            # Rough time estimates (very approximate)
            if method == 'keyset':
                # Keyset pagination is more efficient
                estimated_seconds = estimated_rows / 1000  # ~1000 rows/second
            else:
                # Offset pagination is slower for large datasets
                estimated_seconds = estimated_rows / 500   # ~500 rows/second
            
            return {
                'estimated_rows': estimated_rows,
                'estimated_seconds': estimated_seconds,
                'extraction_method': method,
                'stable_key_available': len(stable_keys) > 0,
                'recommended_batch_size': self.default_batch_size,
                'adapter': adapter_type
            }
            
        except Exception as e:
            logger.error("Extraction time estimation failed", error=str(e))
            return {
                'estimated_rows': 0,
                'estimated_seconds': 0,
                'extraction_method': 'unknown',
                'stable_key_available': False,
                'error': str(e)
            }
    
    def validate_extraction_params(self, adapter_type: str, connection_params: Dict[str, Any],
                                 schema: str, table_name: str, 
                                 columns: List[str]) -> Dict[str, Any]:
        """Validate extraction parameters."""
        try:
            adapter = self.factory.create_adapter(adapter_type)
            
            # Check if table exists
            table_info = adapter.get_table_info(connection_params, schema, table_name)
            if not table_info.columns:
                return {
                    'valid': False,
                    'error': f'Table {schema}.{table_name} not found or has no columns'
                }
            
            # Check if columns exist
            available_columns = [col.name for col in table_info.columns]
            invalid_columns = [col for col in columns if col not in available_columns]
            
            if invalid_columns:
                return {
                    'valid': False,
                    'error': f'Invalid columns: {", ".join(invalid_columns)}',
                    'available_columns': available_columns
                }
            
            # Check for stable key availability
            stable_keys = adapter.get_stable_key_columns(connection_params, schema, table_name)
            
            return {
                'valid': True,
                'stable_key_available': len(stable_keys) > 0,
                'stable_keys': stable_keys,
                'recommended_stable_key': stable_keys[0] if stable_keys else None,
                'table_columns': available_columns
            }
            
        except Exception as e:
            logger.error("Parameter validation failed", error=str(e))
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }


# Global database extractor instance
db_extractor = DatabaseExtractor()
