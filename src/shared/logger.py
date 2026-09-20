"""Secret-safe structured logging for the application."""
import logging
import sys
from typing import Any, Dict, Optional

import structlog


def configure_logging(debug: bool = False) -> None:
    """Configure structured logging that never exposes secrets."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Custom processor to sanitize sensitive data
            sanitize_sensitive_data,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def sanitize_sensitive_data(logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive data from log events."""
    sensitive_keys = {
        'password', 'secret', 'key', 'token', 'auth', 'credential',
        'api_key', 'private_key', 'access_token', 'refresh_token',
        'openai_api_key', 'postgres_password', 'secret_key'
    }
    
    def sanitize_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, str) and len(value) > 20:
            # Potential key/secret pattern
            return "***REDACTED***"
        elif isinstance(value, list):
            return [sanitize_value(item) for item in value]
        return value
    
    # Remove sensitive keys
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = "***REDACTED***"
        elif isinstance(event_dict[key], dict):
            event_dict[key] = sanitize_value(event_dict[key])
    
    return event_dict


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name or __name__)
