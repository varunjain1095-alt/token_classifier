"""PostgreSQL database adapter implementation."""
import psycopg2
import psycopg2.extras
from typing import List, Dict, Any, Optional, Tuple
import time

from src.shared.logger import get_logger
from .base import DatabaseAdapter, TableInfo, ColumnInfo, FilterCondition, QueryResult

logger = get_logger(__name__)


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter."""
    
    def __init__(self):
        self.connection_timeout = 15
        self.query_timeout = 30
    
    def test_connection(self, connection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Test PostgreSQL connection."""
        try:
            conn = psycopg2.connect(
                host=connection_params.get('host', 'localhost'),
                port=connection_params.get('port', 5432),
                database=connection_params.get('database'),
                user=connection_params.get('user'),
                password=connection_params.get('password'),
                connect_timeout=self.connection_timeout
            )
            
            # Test with a simple query
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            cursor.close()
            conn.close()
            
            logger.info("PostgreSQL connection successful", 
                       host=connection_params.get('host'),
                       database=connection_params.get('database'))
            
            return {
                'success': True,
                'message': 'Connection successful',
                'version': version[0] if version else 'Unknown',
                'adapter': 'postgresql'
            }
            
        except Exception as e:
            logger.error("PostgreSQL connection failed", 
                        error=str(e),
                        host=connection_params.get('host'),
                        database=connection_params.get('database'))
            
            return {
                'success': False,
                'error': str(e),
                'adapter': 'postgresql'
            }
    
    def get_schemas(self, connection_params: Dict[str, Any]) -> List[str]:
        """Get list of available schemas."""
        try:
            conn = self._get_connection(connection_params)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                ORDER BY schema_name
            """)
            
            schemas = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            
            logger.info("Retrieved schemas", schemas=schemas)
            return schemas
            
        except Exception as e:
            logger.error("Failed to get schemas", error=str(e))
            return []
    
    def get_tables(self, connection_params: Dict[str, Any], schema: str) -> List[TableInfo]:
        """Get list of tables and views in a schema."""
        try:
            conn = self._get_connection(connection_params)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    table_name,
                    table_type,
                    (SELECT COUNT(*) 
                     FROM information_schema.columns 
                     WHERE table_schema = t.table_schema 
                     AND table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE table_schema = %s
                ORDER BY table_name
            """, (schema,))
            
            tables = []
            for row in cursor.fetchall():
                table_name, table_type, column_count = row
                
                # Get column information
                columns = self._get_table_columns(cursor, schema, table_name)
                
                # Get estimated row count
                estimated_rows = self._get_estimated_row_count(cursor, schema, table_name)
                
                tables.append(TableInfo(
                    schema=schema,
                    name=table_name,
                    type=table_type.lower(),
                    columns=columns,
                    estimated_rows=estimated_rows
                ))
            
            cursor.close()
            conn.close()
            
            logger.info("Retrieved tables", schema=schema, count=len(tables))
            return tables
            
        except Exception as e:
            logger.error("Failed to get tables", error=str(e), schema=schema)
            return []
    
    def get_table_info(self, connection_params: Dict[str, Any], schema: str, table_name: str) -> TableInfo:
        """Get detailed information about a specific table."""
        try:
            conn = self._get_connection(connection_params)
            cursor = conn.cursor()
            
            # Get table type
            cursor.execute("""
                SELECT table_type
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """, (schema, table_name))
            
            result = cursor.fetchone()
            table_type = result[0].lower() if result else 'table'
            
            # Get columns
            columns = self._get_table_columns(cursor, schema, table_name)
            
            # Get estimated row count
            estimated_rows = self._get_estimated_row_count(cursor, schema, table_name)
            
            cursor.close()
            conn.close()
            
            return TableInfo(
                schema=schema,
                name=table_name,
                type=table_type,
                columns=columns,
                estimated_rows=estimated_rows
            )
            
        except Exception as e:
            logger.error("Failed to get table info", error=str(e), 
                        schema=schema, table_name=table_name)
            return TableInfo(schema=schema, name=table_name, type='table', columns=[])
    
    def get_preview_data(self, connection_params: Dict[str, Any], schema: str, table_name: str,
                         columns: List[str], filters: List[FilterCondition],
                         limit: int = 100, offset: int = 0) -> QueryResult:
        """Get bounded preview data from a table."""
        try:
            conn = self._get_connection(connection_params)
            cursor = conn.cursor()
            
            # Build query
            column_list = ', '.join([f'"{col}"' for col in columns]) if columns else '*'
            where_clause = self._build_where_clause(filters)
            query = f'''
                SELECT {column_list}
                FROM "{schema}"."{table_name}"
                {where_clause}
                LIMIT %s OFFSET %s
            '''
            
            params = self._get_filter_values(filters) + [limit, offset]
            cursor.execute(query, params)
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Check if there are more rows
            has_more = len(rows) == limit
            
            cursor.close()
            conn.close()
            
            return QueryResult(
                rows=rows,
                columns=columns,
                row_count=len(rows),
                has_more=has_more
            )
            
        except Exception as e:
            logger.error("Failed to get preview data", error=str(e),
                        schema=schema, table_name=table_name)
            return QueryResult(rows=[], columns=[], row_count=0, has_more=False)
    
    def get_row_count(self, connection_params: Dict[str, Any], schema: str, table_name: str,
                      filters: List[FilterCondition]) -> Dict[str, Any]:
        """Get row count with exact/estimated/unknown status."""
        try:
            conn = self._get_connection(connection_params)
            cursor = conn.cursor()
            
            # Try exact count first (for small tables)
            where_clause = self._build_where_clause(filters)
            count_query = f'''
                SELECT COUNT(*)
                FROM "{schema}"."{table_name}"
                {where_clause}
            '''
            
            params = self._get_filter_values(filters)
            
            try:
                cursor.execute(count_query, params)
                exact_count = cursor.fetchone()[0]
                
                cursor.close()
                conn.close()
                
                return {
                    'count': exact_count,
                    'status': 'exact',
                    'method': 'count_query'
                }
                
            except Exception as e:
                # Fallback to estimated count
                estimated_count = self._get_estimated_row_count(cursor, schema, table_name)
                cursor.close()
                conn.close()
                
                return {
                    'count': estimated_count or 0,
                    'status': 'estimated',
                    'method': 'pg_class_reltuples',
                    'note': 'Exact count failed, using estimate'
                }
            
        except Exception as e:
            logger.error("Failed to get row count", error=str(e),
                        schema=schema, table_name=table_name)
            return {
                'count': 0,
                'status': 'unknown',
                'method': 'error',
                'error': str(e)
            }
    
    def get_stable_key_columns(self, connection_params: Dict[str, Any], schema: str, table_name: str) -> List[str]:
        """Get columns that can be used for stable pagination."""
        try:
            conn = self._get_connection(connection_params)
            cursor = conn.cursor()
            
            # Look for primary key columns
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                    AND tc.table_name = kcu.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
            """, (schema, table_name))
            
            primary_keys = [row[0] for row in cursor.fetchall()]
            
            # If no primary key, look for unique constraints
            if not primary_keys:
                cursor.execute("""
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                        AND tc.table_name = kcu.table_name
                    WHERE tc.constraint_type = 'UNIQUE'
                        AND tc.table_schema = %s
                        AND tc.table_name = %s
                    ORDER BY kcu.ordinal_position
                """, (schema, table_name))
                
                unique_keys = [row[0] for row in cursor.fetchall()]
                primary_keys = unique_keys
            
            # If still no keys, look for indexed columns
            if not primary_keys:
                cursor.execute("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_class c ON c.oid = i.indrelid
                    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s
                    AND c.relname = %s
                    AND i.indisunique = true
                    ORDER BY array_position(i.indkey, a.attnum)
                """, (schema, table_name))
                
                indexed_columns = [row[0] for row in cursor.fetchall()]
                primary_keys = indexed_columns
            
            cursor.close()
            conn.close()
            
            logger.info("Found stable key columns", 
                       schema=schema, table_name=table_name, columns=primary_keys)
            return primary_keys
            
        except Exception as e:
            logger.error("Failed to get stable key columns", error=str(e),
                        schema=schema, table_name=table_name)
            return []
    
    def extract_data(self, connection_params: Dict[str, Any], schema: str, table_name: str,
                    columns: List[str], filters: List[FilterCondition],
                    stable_key: Optional[str] = None, last_key_value: Optional[Any] = None,
                    limit: int = 1000) -> QueryResult:
        """Extract data with pagination support."""
        try:
            conn = self._get_connection(connection_params)
            cursor = conn.cursor()
            
            # Build query
            column_list = ', '.join([f'"{col}"' for col in columns]) if columns else '*'
            where_clause = self._build_where_clause(filters)
            
            # Add stable key condition if provided
            if stable_key and last_key_value is not None:
                if where_clause:
                    where_clause += f' AND "{stable_key}" > %s'
                else:
                    where_clause = f'WHERE "{stable_key}" > %s'
                params = self._get_filter_values(filters) + [last_key_value]
            else:
                params = self._get_filter_values(filters)
            
            # Add ordering for stable pagination
            order_clause = f'ORDER BY "{stable_key}"' if stable_key else 'ORDER BY 1'
            
            query = f'''
                SELECT {column_list}
                FROM "{schema}"."{table_name}"
                {where_clause}
                {order_clause}
                LIMIT %s
            '''
            
            params.append(limit)
            cursor.execute(query, params)
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Check if there are more rows
            has_more = len(rows) == limit
            
            # Get the last key value for next page
            next_key_value = None
            if stable_key and rows:
                key_index = columns.index(stable_key) if stable_key in columns else 0
                next_key_value = rows[-1][key_index] if len(rows) > 0 else None
            
            cursor.close()
            conn.close()
            
            return QueryResult(
                rows=rows,
                columns=columns,
                row_count=len(rows),
                has_more=has_more,
                total_count=next_key_value  # Store as metadata for pagination
            )
            
        except Exception as e:
            logger.error("Failed to extract data", error=str(e),
                        schema=schema, table_name=table_name)
            return QueryResult(rows=[], columns=[], row_count=0, has_more=False)
    
    def supports_read_only_transactions(self) -> bool:
        """Check if adapter supports read-only transactions."""
        return True
    
    def get_adapter_name(self) -> str:
        """Get adapter name."""
        return "PostgreSQL"
    
    def _get_connection(self, connection_params: Dict[str, Any]):
        """Get database connection."""
        return psycopg2.connect(
            host=connection_params.get('host', 'localhost'),
            port=connection_params.get('port', 5432),
            database=connection_params.get('database'),
            user=connection_params.get('user'),
            password=connection_params.get('password'),
            connect_timeout=self.connection_timeout
        )
    
    def _get_table_columns(self, cursor, schema: str, table_name: str) -> List[ColumnInfo]:
        """Get column information for a table."""
        cursor.execute("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                (SELECT COUNT(*) 
                 FROM information_schema.table_constraints tc
                 JOIN information_schema.key_column_usage kcu
                     ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                     AND tc.table_name = kcu.table_name
                     AND kcu.column_name = c.column_name
                 WHERE tc.constraint_type = 'PRIMARY KEY'
                     AND tc.table_schema = c.table_schema
                     AND tc.table_name = c.table_name) as is_primary_key
            FROM information_schema.columns c
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table_name))
        
        columns = []
        for row in cursor.fetchall():
            name, data_type, is_nullable, default, max_length, is_pk = row
            columns.append(ColumnInfo(
                name=name,
                data_type=data_type,
                is_nullable=is_nullable == 'YES',
                is_primary_key=is_pk > 0,
                default_value=default,
                max_length=max_length
            ))
        
        return columns
    
    def _get_estimated_row_count(self, cursor, schema: str, table_name: str) -> Optional[int]:
        """Get estimated row count from pg_class."""
        try:
            cursor.execute("""
                SELECT reltuples::bigint
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
            """, (schema, table_name))
            
            result = cursor.fetchone()
            return result[0] if result and result[0] >= 0 else None
        except:
            return None
    
    def _build_where_clause(self, filters: List[FilterCondition]) -> str:
        """Build WHERE clause from filter conditions."""
        if not filters:
            return ""
        
        conditions = []
        for filter_cond in filters:
            column = f'"{filter_cond.column}"'
            
            if filter_cond.operator == 'IN':
                if isinstance(filter_cond.value, list):
                    placeholders = ', '.join(['%s'] * len(filter_cond.value))
                    conditions.append(f"{column} IN ({placeholders})")
                else:
                    conditions.append(f"{column} = %s")
            elif filter_cond.operator == 'BETWEEN':
                conditions.append(f"{column} BETWEEN %s AND %s")
            elif filter_cond.operator == 'LIKE':
                conditions.append(f"{column} LIKE %s")
            else:
                conditions.append(f"{column} {filter_cond.operator} %s")
        
        return "WHERE " + " AND ".join(conditions)
    
    def _get_filter_values(self, filters: List[FilterCondition]) -> List[Any]:
        """Get filter values for query parameters."""
        values = []
        for filter_cond in filters:
            if filter_cond.operator == 'IN' and isinstance(filter_cond.value, list):
                values.extend(filter_cond.value)
            elif filter_cond.operator == 'BETWEEN' and isinstance(filter_cond.value, list):
                values.extend(filter_cond.value)
            else:
                values.append(filter_cond.value)
        return values
