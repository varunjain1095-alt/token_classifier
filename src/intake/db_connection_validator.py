"""Database connection validation."""
from typing import Dict, Any, Optional
from src.shared.logger import get_logger
from .db_adapters.base import DatabaseAdapterFactory, DatabaseAdapter

logger = get_logger(__name__)


class DatabaseConnectionValidator:
    """Validates database connections."""
    
    def __init__(self):
        self.factory = DatabaseAdapterFactory()
    
    def validate_connection(self, adapter_type: str, connection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate database connection."""
        try:
            # Create adapter
            adapter = self.factory.create_adapter(adapter_type)
            
            # Test connection
            result = adapter.test_connection(connection_params)
            
            if result['success']:
                logger.info("Database connection validated", 
                           adapter=adapter_type,
                           host=connection_params.get('host'))
            else:
                logger.warning("Database connection failed", 
                              adapter=adapter_type,
                              error=result.get('error'))
            
            return result
            
        except Exception as e:
            logger.error("Connection validation error", 
                        adapter=adapter_type,
                        error=str(e))
            return {
                'success': False,
                'error': f'Validation error: {str(e)}',
                'adapter': adapter_type
            }
    
    def get_supported_adapters(self) -> list:
        """Get list of supported database adapters."""
        return self.factory.get_supported_adapters()
    
    def validate_connection_params(self, adapter_type: str, connection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate connection parameters."""
        required_params = {
            'postgresql': ['host', 'port', 'database', 'user', 'password']
        }
        
        required = required_params.get(adapter_type, [])
        missing = [param for param in required if not connection_params.get(param)]
        
        if missing:
            return {
                'valid': False,
                'error': f'Missing required parameters: {", ".join(missing)}'
            }
        
        # Validate port number
        try:
            port = int(connection_params.get('port', 5432))
            if not (1 <= port <= 65535):
                return {
                    'valid': False,
                    'error': 'Invalid port number'
                }
        except ValueError:
            return {
                'valid': False,
                'error': 'Port must be a number'
            }
        
        return {'valid': True}


# Global connection validator instance
connection_validator = DatabaseConnectionValidator()
