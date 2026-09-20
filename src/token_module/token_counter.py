"""Token counting using tiktoken for OpenAI models."""
import tiktoken
from typing import Dict, Any, List, Optional
from enum import Enum

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__)


class TokenEncoding(Enum):
    """Token encoding types."""
    CL100K_BASE = "cl100k_base"  # GPT-4, GPT-3.5-turbo
    P50K_BASE = "p50k_base"      # GPT-3.5-turbo (older)
    R50K_BASE = "r50k_base"      # GPT-3


class TokenCounter:
    """Token counter using tiktoken."""
    
    def __init__(self):
        self.encodings = {}
        self.default_model = get_settings().openai_model_name
        self.default_encoding = tiktoken.get_encoding('cl100k_base')
        self._initialize_encodings()
    
    def _initialize_encodings(self):
        """Initialize tiktoken encodings."""
        try:
            # Initialize encodings for different models
            self.encodings = {
                'gpt-4o-mini': tiktoken.get_encoding('cl100k_base'),
                'gpt-4o': tiktoken.get_encoding('cl100k_base'),
                'gpt-4': tiktoken.get_encoding('cl100k_base'),
                'gpt-3.5-turbo': tiktoken.get_encoding('cl100k_base'),
                'text-davinci-003': tiktoken.get_encoding('p50k_base'),
            }
            logger.info("Token encodings initialized", encodings=list(self.encodings.keys()))
        except Exception as e:
            logger.error("Failed to initialize token encodings", error=str(e))
            # Fallback to cl100k_base
            self.encodings['default'] = tiktoken.get_encoding('cl100k_base')
    
    def count_tokens(self, text: str, model: str = None) -> int:
        """Count tokens in text for specific model."""
        model = model or self.default_model
        try:
            # All current chat models share cl100k_base; fall back to it
            # for models not explicitly mapped.
            encoding = self.encodings.get(model, self.default_encoding)
            
            tokens = encoding.encode(text)
            return len(tokens)
            
        except Exception as e:
            logger.error("Token counting failed", error=str(e), model=model)
            return len(text.split())  # Fallback to word count
    
    def count_message_tokens(self, messages: List[Dict[str, str]], model: str = None) -> int:
        model = model or self.default_model
        """Count tokens in message array."""
        try:
            total_tokens = 0
            
            # Count tokens for each message
            for message in messages:
                # Count role tokens
                total_tokens += self.count_tokens(message.get('role', ''), model)
                
                # Count content tokens
                content = message.get('content', '')
                total_tokens += self.count_tokens(content, model)
                
                # Add overhead for message structure
                total_tokens += 3  # <|start|>, role, <|end|>
            
            # Add overhead for conversation structure
            total_tokens += 3  # <|start|>assistant<|message|>
            
            logger.info("Message tokens counted", 
                       message_count=len(messages),
                       total_tokens=total_tokens,
                       model=model)
            
            return total_tokens
            
        except Exception as e:
            logger.error("Message token counting failed", error=str(e))
            return sum(len(msg.get('content', '').split()) for msg in messages)
    
    def estimate_completion_tokens(self, max_tokens: int, output_format: str = 'json') -> int:
        """Estimate completion tokens based on max_tokens and format."""
        try:
            # For JSON format, we expect structured output
            if output_format in ('json', 'json_object', 'json_schema'):
                # JSON responses typically use fewer tokens due to structure
                estimated = min(max_tokens, 200)  # Conservative estimate
            else:
                # Text responses might use more tokens
                estimated = min(max_tokens, 300)  # Conservative estimate
            
            logger.info("Completion tokens estimated", 
                       max_tokens=max_tokens,
                       estimated_tokens=estimated,
                       output_format=output_format)
            
            return estimated
            
        except Exception as e:
            logger.error("Completion token estimation failed", error=str(e))
            return min(max_tokens, 100)  # Conservative fallback
    
    def estimate_request_tokens(self, payload: Dict[str, Any]) -> Dict[str, int]:
        """Estimate total tokens for a request."""
        try:
            model = payload.get('model', self.default_model)
            messages = payload.get('messages', [])
            max_tokens = payload.get('max_tokens', 150)
            output_format = payload.get('response_format', {}).get('type', 'text')
            
            # Count input tokens
            input_tokens = self.count_message_tokens(messages, model)
            
            # Estimate output tokens
            output_tokens = self.estimate_completion_tokens(max_tokens, output_format)
            
            total_tokens = input_tokens + output_tokens
            
            result = {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'model': model
            }
            
            logger.info("Request tokens estimated", 
                       input_tokens=input_tokens,
                       output_tokens=output_tokens,
                       total_tokens=total_tokens,
                       model=model)
            
            return result
            
        except Exception as e:
            logger.error("Request token estimation failed", error=str(e))
            return {
                'input_tokens': 100,  # Conservative fallback
                'output_tokens': 50,
                'total_tokens': 150,
                'model': 'unknown'
            }
    
    def get_token_ranges(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get token range estimates (low, base, high)."""
        try:
            base_estimate = self.estimate_request_tokens(payload)
            
            # Create ranges based on uncertainty
            low_estimate = {
                'input_tokens': int(base_estimate['input_tokens'] * 0.8),
                'output_tokens': int(base_estimate['output_tokens'] * 0.7),
                'total_tokens': int(base_estimate['total_tokens'] * 0.75)
            }
            
            high_estimate = {
                'input_tokens': int(base_estimate['input_tokens'] * 1.2),
                'output_tokens': int(base_estimate['output_tokens'] * 1.5),
                'total_tokens': int(base_estimate['total_tokens'] * 1.4)
            }
            
            result = {
                'low': low_estimate,
                'base': base_estimate,
                'high': high_estimate,
                'model': base_estimate['model']
            }
            
            logger.info("Token ranges estimated", 
                       low_total=low_estimate['total_tokens'],
                       base_total=base_estimate['total_tokens'],
                       high_total=high_estimate['total_tokens'])
            
            return result
            
        except Exception as e:
            logger.error("Token range estimation failed", error=str(e))
            return {
                'low': {'input_tokens': 80, 'output_tokens': 35, 'total_tokens': 115},
                'base': {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150},
                'high': {'input_tokens': 120, 'output_tokens': 75, 'total_tokens': 195},
                'model': 'unknown'
            }


# Global token counter instance
token_counter = TokenCounter()
