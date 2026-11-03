"""OpenAI API provider for classification requests."""
import openai
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from src.shared.logger import get_logger
from src.shared.config import get_settings

logger = get_logger(__name__)


class ProviderStatus(Enum):
    """Provider status."""
    AVAILABLE = "available"
    QUOTA_EXCEEDED = "quota_exceeded"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class OpenAIProvider:
    """OpenAI API provider for classification requests."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self.default_model = self.settings.openai_model_name
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 60.0
        
    def initialize_client(self, api_key: str = None):
        """Initialize OpenAI client with API key."""
        try:
            # Use provided API key or fall back to settings
            key = api_key or self.settings.openai_api_key
            if not key:
                logger.error("No OpenAI API key provided")
                return False
            
            self.client = openai.AsyncOpenAI(api_key=key)
            logger.info("OpenAI client initialized", model=self.default_model)
            return True
            
        except Exception as e:
            logger.error("Failed to initialize OpenAI client", error=str(e))
            return False
    
    def _client_for(self, api_key: str = None):
        """Resolve the client for a call.

        A per-call key gets a dedicated client so one user's key never
        leaks into the shared client used by other requests.
        """
        if api_key:
            try:
                return openai.AsyncOpenAI(api_key=api_key)
            except Exception as e:
                logger.error("Failed to create per-call OpenAI client", error=str(e))
                return None
        return self.client

    async def classify_single(self, payload: Dict[str, Any],
                            request_id: str = None,
                            api_key: str = None) -> Dict[str, Any]:
        """Classify a single request."""
        try:
            client = self._client_for(api_key)
            if not client:
                return {
                    'success': False,
                    'error': 'OpenAI client not initialized',
                    'provider_status': ProviderStatus.ERROR.value
                }

            # Make API call with retry logic
            response = await self._make_request_with_retry(payload, client)
            
            if response['success']:
                # Extract classification result
                result = self._extract_classification_result(response['data'])
                
                logger.info("Classification completed", 
                           request_id=request_id,
                           model=payload.get('model'),
                           usage=response.get('usage', {}))
                
                return {
                    'success': True,
                    'result': result,
                    'usage': response.get('usage', {}),
                    'model': payload.get('model'),
                    'provider_status': ProviderStatus.AVAILABLE.value
                }
            else:
                return {
                    'success': False,
                    'error': response['error'],
                    'provider_status': response.get('provider_status', ProviderStatus.ERROR.value)
                }
                
        except Exception as e:
            logger.error("Classification failed", error=str(e), request_id=request_id)
            return {
                'success': False,
                'error': str(e),
                'provider_status': ProviderStatus.ERROR.value
            }
    
    async def classify_batch(self, payloads: List[Dict[str, Any]],
                           batch_id: str = None,
                           api_key: str = None) -> Dict[str, Any]:
        """Classify a batch of requests."""
        try:
            if not self._client_for(api_key):
                return {
                    'success': False,
                    'error': 'OpenAI client not initialized',
                    'provider_status': ProviderStatus.ERROR.value
                }

            results = []
            successful = 0
            failed = 0

            # Process requests in parallel with rate limiting
            semaphore = asyncio.Semaphore(5)  # Limit concurrent requests

            async def process_single(payload, index):
                async with semaphore:
                    request_id = f"{batch_id}_{index}" if batch_id else f"batch_{index}"
                    return await self.classify_single(payload, request_id, api_key=api_key)
            
            # Create tasks for all payloads
            tasks = [process_single(payload, i) for i, payload in enumerate(payloads)]
            
            # Execute all tasks
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append({
                        'success': False,
                        'error': str(result),
                        'index': i
                    })
                    failed += 1
                else:
                    results.append(result)
                    if result['success']:
                        successful += 1
                    else:
                        failed += 1
            
            logger.info("Batch classification completed", 
                       batch_id=batch_id,
                       total=len(payloads),
                       successful=successful,
                       failed=failed)
            
            return {
                'success': True,
                'results': results,
                'summary': {
                    'total': len(payloads),
                    'successful': successful,
                    'failed': failed,
                    'success_rate': (successful / len(payloads)) * 100 if payloads else 0
                },
                'provider_status': ProviderStatus.AVAILABLE.value
            }
            
        except Exception as e:
            logger.error("Batch classification failed", error=str(e), batch_id=batch_id)
            return {
                'success': False,
                'error': str(e),
                'provider_status': ProviderStatus.ERROR.value
            }
    
    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt request parameters to the configured model's API rules.

        Newer models (gpt-5 family, o-series) reject `max_tokens` in favour of
        `max_completion_tokens`, and do not accept a custom `temperature`.
        """
        normalized = dict(payload)
        model = str(normalized.get('model', ''))

        if 'max_tokens' in normalized:
            normalized['max_completion_tokens'] = normalized.pop('max_tokens')

        restricted_temperature = model.startswith(('gpt-5', 'o1', 'o3', 'o4'))
        if restricted_temperature:
            normalized.pop('temperature', None)
            # Reasoning models spend completion tokens on hidden reasoning;
            # cap the effort and guarantee enough budget for actual output.
            normalized.setdefault('reasoning_effort', 'minimal')
            existing = normalized.get('max_completion_tokens', 0)
            normalized['max_completion_tokens'] = max(existing, 1500)

        return normalized

    async def _make_request_with_retry(self, payload: Dict[str, Any],
                                       client=None) -> Dict[str, Any]:
        """Make API request with exponential backoff retry."""
        last_error = None
        payload = self._normalize_payload(payload)
        client = client or self.client

        for attempt in range(self.max_retries):
            try:
                response = await client.chat.completions.create(**payload)
                
                return {
                    'success': True,
                    'data': response,
                    'usage': {
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens,
                        'total_tokens': response.usage.total_tokens
                    }
                }
                
            except openai.RateLimitError as e:
                last_error = e
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning("Rate limit hit, retrying", 
                             attempt=attempt + 1,
                             delay=delay)
                await asyncio.sleep(delay)
                
            except openai.APIError as e:
                last_error = e
                if e.status_code >= 500:  # Server error, retry
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    logger.warning("API error, retrying", 
                                 attempt=attempt + 1,
                                 error=str(e),
                                 delay=delay)
                    await asyncio.sleep(delay)
                else:  # Client error, don't retry
                    logger.error("Client error, not retrying", error=str(e))
                    break
                    
            except Exception as e:
                last_error = e
                logger.error("Unexpected error", error=str(e))
                break
        
        # All retries failed
        error_msg = str(last_error) if last_error else "Unknown error"
        
        # Determine provider status based on error
        if "rate limit" in error_msg.lower():
            provider_status = ProviderStatus.RATE_LIMITED.value
        elif "quota" in error_msg.lower() or "insufficient" in error_msg.lower():
            provider_status = ProviderStatus.QUOTA_EXCEEDED.value
        else:
            provider_status = ProviderStatus.ERROR.value
        
        return {
            'success': False,
            'error': error_msg,
            'provider_status': provider_status
        }
    
    def _extract_classification_result(self, response: Any) -> Dict[str, Any]:
        """Extract classification result from OpenAI response."""
        try:
            content = response.choices[0].message.content
            
            # Try to parse as JSON if response format is JSON
            if content.startswith('{') and content.endswith('}'):
                import json
                try:
                    parsed = json.loads(content)
                    return {
                        'classification': parsed,
                        'raw_content': content,
                        'format': 'json'
                    }
                except json.JSONDecodeError:
                    pass
            
            # Return as text result
            return {
                'classification': content,
                'raw_content': content,
                'format': 'text'
            }
            
        except Exception as e:
            logger.error("Failed to extract classification result", error=str(e))
            return {
                'classification': 'Error extracting result',
                'raw_content': str(response),
                'format': 'error'
            }
    
    async def test_connection(self, api_key: str = None) -> Dict[str, Any]:
        """Test OpenAI API connection."""
        try:
            client = self._client_for(api_key)
            if not client:
                return {
                    'success': False,
                    'error': 'Client not initialized'
                }

            # Make a simple test request (normalized for the configured model)
            test_payload = self._normalize_payload({
                'model': self.default_model,
                'messages': [{'role': 'user', 'content': 'Hello'}],
                'max_tokens': 5
            })

            response = await client.chat.completions.create(**test_payload)
            
            logger.info("OpenAI connection test successful")
            
            return {
                'success': True,
                'model': self.default_model,
                'response_id': response.id,
                'provider_status': ProviderStatus.AVAILABLE.value
            }
            
        except Exception as e:
            logger.error("OpenAI connection test failed", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'provider_status': ProviderStatus.ERROR.value
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about available models."""
        return {
            'default_model': self.default_model,
            'supported_models': [self.default_model],
            'max_retries': self.max_retries,
            'base_delay': self.base_delay,
            'max_delay': self.max_delay
        }


# Global OpenAI provider instance
openai_provider = OpenAIProvider()
