"""Base database adapter interface."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TableInfo:
    """Information about a database table."""
    schema: str
    name: str
    type: str  # 'table', 'view', 'materialized_view'
    columns: List[Dict[str, Any]]
    estimated_rows: Optional[int] = None


@dataclass
class ColumnInfo:
    """Information about a database column."""
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    default_value: Optional[str] = None
    max_length: Optional[int] = None


@dataclass
class FilterCondition:
    """Database filter condition."""
    column: str
    operator: str  # '=', '!=', '>', '<', '>=', '<=', 'LIKE', 'IN', 'BETWEEN'
    value: Any
    value_type: str  # 'string', 'number', 'date', 'boolean'


@dataclass
class QueryResult:
    """Result of a database query."""
    rows: List[List[Any]]
    columns: List[str]
    row_count: int
    has_more: bool
    total_count: Optional[int] = None


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""
    
    @abstractmethod
    def test_connection(self, connection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Test database connection without reading data."""
        pass
    
    @abstractmethod
    def get_schemas(self, connection_params: Dict[str, Any]) -> List[str]:
        """Get list of available schemas."""
        pass
    
    @abstractmethod
    def get_tables(self, connection_params: Dict[str, Any], schema: str) -> List[TableInfo]:
        """Get list of tables and views in a schema."""
        pass
    
    @abstractmethod
    def get_table_info(self, connection_params: Dict[str, Any], schema: str, table_name: str) -> TableInfo:
        """Get detailed information about a specific table."""
        pass
    
    @abstractmethod
    def get_preview_data(self, connection_params: Dict[str, Any], schema: str, table_name: str,
                         columns: List[str], filters: List[FilterCondition],
                         limit: int = 100, offset: int = 0) -> QueryResult:
        """Get bounded preview data from a table."""
        pass
    
    @abstractmethod
    def get_row_count(self, connection_params: Dict[str, Any], schema: str, table_name: str,
                      filters: List[FilterCondition]) -> Dict[str, Any]:
        """Get row count with exact/estimated/unknown status."""
        pass
    
    @abstractmethod
    def get_stable_key_columns(self, connection_params: Dict[str, Any], schema: str, table_name: str) -> List[str]:
        """Get columns that can be used for stable pagination."""
        pass
    
    @abstractmethod
    def extract_data(self, connection_params: Dict[str, Any], schema: str, table_name: str,
                    columns: List[str], filters: List[FilterCondition],
                    stable_key: Optional[str] = None, last_key_value: Optional[Any] = None,
                    limit: int = 1000) -> QueryResult:
        """Extract data with pagination support."""
        pass
    
    @abstractmethod
    def supports_read_only_transactions(self) -> bool:
        """Check if adapter supports read-only transactions."""
        pass
    
    @abstractmethod
    def get_adapter_name(self) -> str:
        """Get adapter name."""
        pass


class DatabaseAdapterFactory:
    """Factory for creating database adapters."""
    
    @staticmethod
    def create_adapter(adapter_type: str) -> DatabaseAdapter:
        """Create a database adapter instance."""
        if adapter_type.lower() == 'postgresql':
            from .postgresql import PostgreSQLAdapter
            return PostgreSQLAdapter()
        else:
            raise ValueError(f"Unsupported database adapter: {adapter_type}")
    
    @staticmethod
    def get_supported_adapters() -> List[str]:
        """Get list of supported database adapters."""
        return ['postgresql']
