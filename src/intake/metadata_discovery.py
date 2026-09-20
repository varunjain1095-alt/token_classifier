"""Database metadata discovery."""
from typing import List, Dict, Any, Optional
from src.shared.logger import get_logger
from .db_adapters.base import DatabaseAdapterFactory, TableInfo, ColumnInfo

logger = get_logger(__name__)


class MetadataDiscovery:
    """Discovers database metadata (schemas, tables, columns)."""
    
    def __init__(self):
        self.factory = DatabaseAdapterFactory()
    
    def discover_schemas(self, adapter_type: str, connection_params: Dict[str, Any]) -> List[str]:
        """Discover available schemas."""
        try:
            adapter = self.factory.create_adapter(adapter_type)
            schemas = adapter.get_schemas(connection_params)
            
            logger.info("Discovered schemas", 
                       adapter=adapter_type,
                       schemas=schemas)
            
            return schemas
            
        except Exception as e:
            logger.error("Schema discovery failed", 
                        adapter=adapter_type,
                        error=str(e))
            return []
    
    def discover_tables(self, adapter_type: str, connection_params: Dict[str, Any], 
                       schema: str) -> List[TableInfo]:
        """Discover tables and views in a schema."""
        try:
            adapter = self.factory.create_adapter(adapter_type)
            tables = adapter.get_tables(connection_params, schema)
            
            logger.info("Discovered tables", 
                       adapter=adapter_type,
                       schema=schema,
                       table_count=len(tables))
            
            return tables
            
        except Exception as e:
            logger.error("Table discovery failed", 
                        adapter=adapter_type,
                        schema=schema,
                        error=str(e))
            return []
    
    def get_table_details(self, adapter_type: str, connection_params: Dict[str, Any],
                         schema: str, table_name: str) -> Optional[TableInfo]:
        """Get detailed information about a specific table."""
        try:
            adapter = self.factory.create_adapter(adapter_type)
            table_info = adapter.get_table_info(connection_params, schema, table_name)
            
            logger.info("Retrieved table details", 
                       adapter=adapter_type,
                       schema=schema,
                       table_name=table_name,
                       column_count=len(table_info.columns))
            
            return table_info
            
        except Exception as e:
            logger.error("Table detail discovery failed", 
                        adapter=adapter_type,
                        schema=schema,
                        table_name=table_name,
                        error=str(e))
            return None
    
    def get_column_types(self, table_info: TableInfo) -> Dict[str, str]:
        """Get column names and their data types."""
        return {col.name: col.data_type for col in table_info.columns}
    
    def get_primary_keys(self, table_info: TableInfo) -> List[str]:
        """Get primary key column names."""
        return [col.name for col in table_info.columns if col.is_primary_key]
    
    def get_nullable_columns(self, table_info: TableInfo) -> List[str]:
        """Get nullable column names."""
        return [col.name for col in table_info.columns if col.is_nullable]
    
    def get_non_nullable_columns(self, table_info: TableInfo) -> List[str]:
        """Get non-nullable column names."""
        return [col.name for col in table_info.columns if not col.is_nullable]
    
    def filter_columns_by_type(self, table_info: TableInfo, 
                              data_types: List[str]) -> List[ColumnInfo]:
        """Filter columns by data type."""
        return [col for col in table_info.columns if col.data_type in data_types]
    
    def get_text_columns(self, table_info: TableInfo) -> List[ColumnInfo]:
        """Get text-based columns suitable for review text."""
        text_types = ['text', 'varchar', 'char', 'character', 'character varying', 'text']
        return self.filter_columns_by_type(table_info, text_types)
    
    def get_numeric_columns(self, table_info: TableInfo) -> List[ColumnInfo]:
        """Get numeric columns."""
        numeric_types = ['integer', 'bigint', 'smallint', 'decimal', 'numeric', 'real', 'double precision', 'serial', 'bigserial']
        return self.filter_columns_by_type(table_info, numeric_types)
    
    def get_date_columns(self, table_info: TableInfo) -> List[ColumnInfo]:
        """Get date/time columns."""
        date_types = ['date', 'timestamp', 'timestamptz', 'time', 'interval']
        return self.filter_columns_by_type(table_info, date_types)
    
    def get_boolean_columns(self, table_info: TableInfo) -> List[ColumnInfo]:
        """Get boolean columns."""
        boolean_types = ['boolean', 'bool']
        return self.filter_columns_by_type(table_info, boolean_types)


# Global metadata discovery instance
metadata_discovery = MetadataDiscovery()
