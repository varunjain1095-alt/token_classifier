"""Session-only secret handling for user credentials."""
import secrets
import time
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import base64
import os

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__)


class SecretHandler:
    """Handles session-only secrets that are never persisted."""
    
    def __init__(self):
        self.settings = get_settings()
        # Generate a key for encrypting secrets in memory
        self._encryption_key = self._generate_encryption_key()
        self._cipher = Fernet(self._encryption_key)
    
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for session secrets."""
        # Use the app's secret key as the base for encryption
        password = self.settings.secret_key.encode()
        salt = b'session_secret_salt'  # Static salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def store_secret(self, session_id: str, secret_type: str, secret_value: str) -> bool:
        """Store a secret in ephemeral session memory."""
        try:
            # Encrypt the secret
            encrypted_secret = self._cipher.encrypt(secret_value.encode())
            
            # Store in Redis with session prefix and short TTL
            redis_key = f"secret:{session_id}:{secret_type}"
            self.settings.redis_url  # This should use redis client instead
            
            # For now, use in-memory storage (in production, use Redis with TTL)
            if not hasattr(self, '_secrets'):
                self._secrets = {}
            
            if session_id not in self._secrets:
                self._secrets[session_id] = {}
            
            self._secrets[session_id][secret_type] = {
                'encrypted_value': encrypted_secret,
                'created_at': time.time()
            }
            
            logger.info("Secret stored in session", 
                       session_id=session_id[:8], 
                       secret_type=secret_type)
            return True
            
        except Exception as e:
            logger.error("Failed to store secret", 
                        session_id=session_id[:8], 
                        secret_type=secret_type,
                        error=str(e))
            return False
    
    def get_secret(self, session_id: str, secret_type: str) -> Optional[str]:
        """Retrieve a secret from ephemeral session memory."""
        try:
            if not hasattr(self, '_secrets') or session_id not in self._secrets:
                return None
            
            if secret_type not in self._secrets[session_id]:
                return None
            
            secret_data = self._secrets[session_id][secret_type]
            
            # Check if secret is expired (session timeout)
            if time.time() - secret_data['created_at'] > self.settings.session_timeout:
                del self._secrets[session_id][secret_type]
                return None
            
            # Decrypt and return
            decrypted_secret = self._cipher.decrypt(secret_data['encrypted_value'])
            return decrypted_secret.decode()
            
        except Exception as e:
            logger.error("Failed to retrieve secret", 
                        session_id=session_id[:8], 
                        secret_type=secret_type,
                        error=str(e))
            return None
    
    def delete_secret(self, session_id: str, secret_type: str) -> bool:
        """Delete a specific secret from session."""
        try:
            if not hasattr(self, '_secrets') or session_id not in self._secrets:
                return False
            
            if secret_type in self._secrets[session_id]:
                del self._secrets[session_id][secret_type]
                logger.info("Secret deleted from session", 
                           session_id=session_id[:8], 
                           secret_type=secret_type)
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to delete secret", 
                        session_id=session_id[:8], 
                        secret_type=secret_type,
                        error=str(e))
            return False
    
    def clear_session_secrets(self, session_id: str) -> bool:
        """Clear all secrets for a session."""
        try:
            if not hasattr(self, '_secrets') or session_id not in self._secrets:
                return False
            
            secret_types = list(self._secrets[session_id].keys())
            del self._secrets[session_id]
            
            logger.info("All secrets cleared for session", 
                       session_id=session_id[:8], 
                       secret_count=len(secret_types))
            return True
            
        except Exception as e:
            logger.error("Failed to clear session secrets", 
                        session_id=session_id[:8], 
                        error=str(e))
            return False
    
    def store_openai_key(self, session_id: str, api_key: str) -> bool:
        """Store user OpenAI API key for session."""
        return self.store_secret(session_id, 'openai_api_key', api_key)
    
    def get_openai_key(self, session_id: str) -> Optional[str]:
        """Retrieve user OpenAI API key from session."""
        return self.get_secret(session_id, 'openai_api_key')
    
    def store_db_credentials(self, session_id: str, credentials: Dict[str, str]) -> bool:
        """Store database credentials for session."""
        # Store as JSON string
        import json
        credentials_json = json.dumps(credentials)
        return self.store_secret(session_id, 'db_credentials', credentials_json)
    
    def get_db_credentials(self, session_id: str) -> Optional[Dict[str, str]]:
        """Retrieve database credentials from session."""
        credentials_json = self.get_secret(session_id, 'db_credentials')
        if not credentials_json:
            return None
        
        try:
            import json
            return json.loads(credentials_json)
        except Exception as e:
            logger.error("Failed to parse database credentials", 
                        session_id=session_id[:8],
                        error=str(e))
            return None
    
    def clear_openai_key(self, session_id: str) -> bool:
        """Clear OpenAI API key from session."""
        return self.delete_secret(session_id, 'openai_api_key')
    
    def clear_db_credentials(self, session_id: str) -> bool:
        """Clear database credentials from session."""
        return self.delete_secret(session_id, 'db_credentials')


# Global secret handler instance
secret_handler = SecretHandler()
