"""Multi-provider pricing catalogue and cost estimation."""
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from src.shared.config import get_settings
from src.shared.logger import get_logger

logger = get_logger(__name__)


class PricingTier(Enum):
    """Pricing tier types."""
    INPUT = "input"
    OUTPUT = "output"
    CACHED_INPUT = "cached_input"


class PricingManager:
    """Manages provider pricing catalogue and cost estimation."""

    ALLOWED_RECORD_FIELDS = {
        'provider', 'provider_name', 'model_id', 'display_name',
        'input_per_million', 'cached_input_per_million',
        'cache_write_per_million', 'cache_write_1h_per_million',
        'output_per_million', 'context_threshold_tokens', 'long_context',
        'batch', 'service_tiers', 'provider_fees',
        'status', 'status_note', 'sunset_date', 'source_url',
        'effective_date', 'last_verified_date'
    }
    PRICE_FIELDS = {
        'input_per_million', 'cached_input_per_million',
        'cache_write_per_million', 'cache_write_1h_per_million',
        'output_per_million'
    }

    def __init__(self):
        self.settings = get_settings()
        self.catalogue = self._load_catalogue()
        self._validate_catalogue(self.catalogue['records'])
        self.records_by_model = {
            r['model_id']: r for r in self.catalogue['records']
        }

    def _load_catalogue(self) -> Dict[str, Any]:
        """Load pricing records from the version-controlled JSON catalogue."""
        path = os.path.join(os.path.dirname(__file__), 'pricing_catalogue.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info("Pricing catalogue loaded",
                       version=data.get('catalogue_version'),
                       records=len(data.get('records', [])))
            return data
        except Exception as e:
            logger.error("Failed to load pricing catalogue", error=str(e))
            return {'catalogue_version': 'unknown', 'records': []}

    def _validate_catalogue(self, records: List[Dict[str, Any]]) -> None:
        """Reject invalid catalogue records at load time.

        Rejects: duplicate model IDs, missing sources, negative prices,
        unsupported fields, and empty/unverifiable model IDs.
        """
        errors = []
        seen_ids = set()
        for i, r in enumerate(records):
            model_id = r.get('model_id')
            label = model_id or f'record[{i}]'

            if not model_id or not isinstance(model_id, str) or not model_id.strip():
                errors.append(f'{label}: missing or empty model_id')
            elif model_id in seen_ids:
                errors.append(f'{label}: duplicate model_id')
            else:
                seen_ids.add(model_id)

            if not r.get('source_url'):
                errors.append(f'{label}: missing source_url')
            if not r.get('provider') or not r.get('provider_name'):
                errors.append(f'{label}: missing provider/provider_name')

            unknown = set(r.keys()) - self.ALLOWED_RECORD_FIELDS
            if unknown:
                errors.append(f'{label}: unsupported fields {sorted(unknown)}')

            def _check_prices(block, ctx):
                for k, v in (block or {}).items():
                    if k in ('description', 'notes', 'status_note'):
                        continue
                    if isinstance(v, (int, float)) and v < 0:
                        errors.append(f'{label}: negative price in {ctx}.{k}')

            _check_prices(r, 'record')
            _check_prices(r.get('long_context'), 'long_context')
            _check_prices(r.get('batch'), 'batch')

            status = r.get('status', 'active')
            if status not in ('active', 'sunsetting', 'deprecated', 'limited'):
                errors.append(f'{label}: invalid status {status!r}')
            if status == 'sunsetting' and not r.get('sunset_date'):
                errors.append(f'{label}: sunsetting record missing sunset_date')
            # Priced records must carry verified token prices
            if status != 'deprecated' and (
                    r.get('input_per_million') is None or r.get('output_per_million') is None):
                errors.append(f'{label}: priced record missing input/output price')

        if errors:
            logger.error("Pricing catalogue validation failed", errors=errors)
            raise ValueError('Invalid pricing catalogue: ' + '; '.join(errors))

    def get_catalogue_records(self) -> List[Dict[str, Any]]:
        """Get all pricing records."""
        return self.catalogue['records']

    def get_model_pricing(self, model: str) -> Optional[Dict[str, Any]]:
        """Get the pricing record for a specific model ID."""
        return self.records_by_model.get(model)

    def get_supported_tiers(self, pricing: Dict[str, Any]) -> List[str]:
        """Service tiers officially available for a catalogue record."""
        tiers = ['standard']
        tiers_meta = pricing.get('service_tiers') or {}
        if pricing.get('batch') or tiers_meta.get('batch'):
            tiers.append('batch')
        if tiers_meta.get('flex'):
            tiers.append('flex')
        return tiers

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int,
                      cached_input_tokens: int = 0,
                      service_tier: str = 'standard') -> Dict[str, Any]:
        """Calculate cost for token usage on the selected model.

        Context tiers are selected using this request's input token count —
        never total tokens across the workload. `service_tier` may be
        'standard' or 'batch' (when the record carries a batch price block).
        """
        try:
            pricing = self.get_model_pricing(model)
            if not pricing:
                logger.warning("No pricing found for model", model=model)
                return {
                    'input_cost': 0.0,
                    'output_cost': 0.0,
                    'cached_input_cost': 0.0,
                    'cached_input_supported': False,
                    'provider_fee_cost': 0.0,
                    'total_cost': 0.0,
                    'currency': 'USD',
                    'model': model
                }

            # Select the per-request price block. Context tier is decided by
            # this request's input tokens — never workload totals. Batch/flex
            # are refused rather than silently falling back to Standard.
            tiers_meta = pricing.get('service_tiers') or {}
            if service_tier not in self.get_supported_tiers(pricing):
                return {
                    'input_cost': 0.0, 'output_cost': 0.0,
                    'cached_input_cost': 0.0, 'cached_input_supported': False,
                    'provider_fee_cost': 0.0, 'total_cost': 0.0,
                    'currency': 'USD', 'model': model,
                    'tier_supported': False,
                    'tier_requested': service_tier,
                    'supported_tiers': self.get_supported_tiers(pricing)
                }

            threshold = pricing.get('context_threshold_tokens')
            over_threshold = bool(
                threshold and pricing.get('long_context') and input_tokens > threshold)
            base = pricing['long_context'] if over_threshold else pricing
            tier_applied = 'long_context' if over_threshold else 'standard'

            rates = base
            if service_tier in ('batch', 'flex'):
                if pricing.get('batch') and not over_threshold:
                    rates = pricing['batch']
                else:
                    # Batch/flex are officially 50% of the applicable
                    # context-tier rate for these providers
                    rates = {
                        k: (v * 0.5 if isinstance(v, (int, float)) else v)
                        for k, v in base.items()
                    }
                tier_applied = (
                    f'{service_tier}_long_context' if over_threshold else service_tier)

            input_rate = rates.get('input_per_million')
            output_rate = rates.get('output_per_million')
            if input_rate is None or output_rate is None:
                return {
                    'input_cost': 0.0, 'output_cost': 0.0,
                    'cached_input_cost': 0.0, 'cached_input_supported': False,
                    'provider_fee_cost': 0.0, 'total_cost': 0.0,
                    'currency': 'USD', 'model': model,
                    'price_unavailable': True
                }

            input_cost = (input_tokens / 1_000_000) * input_rate
            output_cost = (output_tokens / 1_000_000) * output_rate

            cached_supported = rates.get('cached_input_per_million') is not None
            cached_input_cost = (
                (cached_input_tokens / 1_000_000) * rates['cached_input_per_million']
                if cached_supported else 0.0
            )

            # Provider-specific charges (e.g., Perplexity search request fee)
            provider_fee_cost = 0.0
            fees = pricing.get('provider_fees') or {}
            fee_per_1k = fees.get('request_fee_per_1k')
            if fee_per_1k:
                provider_fee_cost = fee_per_1k.get('low', 0.0) / 1000

            total_cost = input_cost + output_cost + cached_input_cost + provider_fee_cost

            result = {
                'input_cost': round(input_cost, 6),
                'output_cost': round(output_cost, 6),
                'cached_input_cost': round(cached_input_cost, 6),
                'cached_input_supported': cached_supported,
                'provider_fee_cost': round(provider_fee_cost, 6),
                'total_cost': round(total_cost, 6),
                'currency': 'USD',
                'model': model,
                'resolved_model_id': pricing['model_id'],
                'applied_rates': {
                    'input_per_million': input_rate,
                    'cached_input_per_million': rates.get('cached_input_per_million'),
                    'output_per_million': output_rate,
                },
                'provider': pricing['provider'],
                'provider_name': pricing['provider_name'],
                'display_name': pricing['display_name'],
                'effective_date': pricing.get('effective_date'),
                'last_verified_date': pricing.get('last_verified_date'),
                'source_url': pricing['source_url'],
                'provider_fees': fees or None,
                'context_threshold_tokens': pricing.get('context_threshold_tokens'),
                'tier_applied': tier_applied,
                'tier_supported': True,
                'tier_requested': service_tier,
                'supported_tiers': self.get_supported_tiers(pricing),
                'cache_write_per_million': rates.get('cache_write_per_million'),
                'service_tiers': pricing.get('service_tiers'),
                'batch': pricing.get('batch'),
                'status': pricing.get('status', 'active'),
                'status_note': pricing.get('status_note'),
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens,
                    'cached_input': cached_input_tokens,
                    'total': input_tokens + output_tokens + cached_input_tokens
                }
            }

            logger.info("Cost calculated",
                       model=model,
                       input_tokens=input_tokens,
                       output_tokens=output_tokens,
                       total_cost=total_cost)

            return result

        except Exception as e:
            logger.error("Cost calculation failed", error=str(e))
            return {
                'input_cost': 0.0,
                'output_cost': 0.0,
                'cached_input_cost': 0.0,
                'total_cost': 0.0,
                'currency': 'USD',
                'model': model
            }

    def estimate_request_cost(self, token_estimate: Dict[str, int],
                              model: Optional[str] = None) -> Dict[str, Any]:
        """Estimate cost for a request based on token estimate.

        The `model` parameter is the estimator's selected comparison model;
        it does not change the model used for preview execution.
        """
        try:
            selected_model = model or token_estimate.get('model', self.settings.openai_model_name)
            input_tokens = token_estimate.get('input_tokens', 0)
            output_tokens = token_estimate.get('output_tokens', 0)

            cost_estimate = self.calculate_cost(selected_model, input_tokens, output_tokens)

            result = {
                'cost_estimate': cost_estimate,
                'token_estimate': token_estimate,
                'model': selected_model,
                'estimated_at': datetime.utcnow().isoformat()
            }

            logger.info("Request cost estimated",
                       model=selected_model,
                       total_cost=cost_estimate['total_cost'],
                       total_tokens=token_estimate['total_tokens'])

            return result

        except Exception as e:
            logger.error("Request cost estimation failed", error=str(e))
            return {
                'cost_estimate': {'total_cost': 0.0, 'currency': 'USD'},
                'token_estimate': token_estimate,
                'model': 'unknown'
            }

    def estimate_workload_cost(self, requests: List[Dict[str, Any]],
                               model: Optional[str] = None) -> Dict[str, Any]:
        """Estimate total cost for a workload of requests on the selected model."""
        try:
            total_cost = 0.0
            total_input_tokens = 0
            total_output_tokens = 0
            total_provider_fees = 0.0
            model_breakdown = {}

            for request in requests:
                token_estimate = request.get('token_estimate', {})
                req_model = model or token_estimate.get('model', self.settings.openai_model_name)
                input_tokens = token_estimate.get('input_tokens', 0)
                output_tokens = token_estimate.get('output_tokens', 0)

                cost = self.calculate_cost(req_model, input_tokens, output_tokens)
                total_cost += cost['total_cost']
                total_provider_fees += cost.get('provider_fee_cost', 0.0)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                if req_model not in model_breakdown:
                    model_breakdown[req_model] = {'cost': 0.0, 'requests': 0}
                model_breakdown[req_model]['cost'] += cost['total_cost']
                model_breakdown[req_model]['requests'] += 1

            result = {
                'total_cost': round(total_cost, 6),
                'total_requests': len(requests),
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'total_tokens': total_input_tokens + total_output_tokens,
                'total_provider_fees': round(total_provider_fees, 6),
                'model_breakdown': model_breakdown,
                'currency': 'USD',
                'estimated_at': datetime.utcnow().isoformat()
            }

            logger.info("Workload cost estimated",
                       total_requests=len(requests),
                       total_cost=total_cost,
                       total_tokens=result['total_tokens'])

            return result

        except Exception as e:
            logger.error("Workload cost estimation failed", error=str(e))
            return {
                'total_cost': 0.0,
                'total_requests': len(requests),
                'currency': 'USD'
            }

    def compare_costs(self, token_estimate: Dict[str, Any],
                      request_count: int,
                      model_ids: List[str],
                      service_tier: str = 'standard') -> Dict[str, Any]:
        """Compare per-request and workload cost across selected models.

        All models are priced against the same tiktoken-based token estimate,
        request count, batching and cache assumptions. Models that do not
        support the requested service tier are reported as unsupported
        rather than silently priced at Standard.
        """
        rows = []
        for model_id in model_ids:
            pricing = self.get_model_pricing(model_id)
            if not pricing:
                rows.append({'model_id': model_id, 'error': 'Model not in catalogue'})
                continue
            cost = self.calculate_cost(
                model_id,
                token_estimate.get('input_tokens', 0),
                token_estimate.get('output_tokens', 0),
                token_estimate.get('cached_input_tokens', 0),
                service_tier=service_tier
            )
            if cost.get('tier_supported') is False:
                rows.append({
                    'model_id': model_id,
                    'provider': pricing['provider'],
                    'provider_name': pricing['provider_name'],
                    'display_name': pricing['display_name'],
                    'status': pricing.get('status', 'active'),
                    'status_note': pricing.get('status_note'),
                    'source_url': pricing['source_url'],
                    'tier_supported': False,
                    'tier_requested': service_tier,
                    'supported_tiers': cost.get('supported_tiers', ['standard']),
                    'error': 'Not supported'
                })
                continue
            if cost.get('price_unavailable'):
                rows.append({
                    'model_id': model_id,
                    'provider': pricing['provider'],
                    'provider_name': pricing['provider_name'],
                    'display_name': pricing['display_name'],
                    'status': pricing.get('status', 'active'),
                    'status_note': pricing.get('status_note'),
                    'source_url': pricing['source_url'],
                    'error': 'Pricing unavailable for this model'
                })
                continue
            workload_cost = cost['total_cost'] * request_count
            rows.append({
                'provider': pricing['provider'],
                'provider_name': pricing['provider_name'],
                'requested_model_id': model_id,
                'resolved_model_id': cost.get('resolved_model_id', pricing['model_id']),
                'model_id': model_id,
                'display_name': pricing['display_name'],
                'applied_rates': cost.get('applied_rates'),
                'input_cost': cost['input_cost'],
                'cached_input_cost': cost['cached_input_cost'],
                'cached_input_supported': cost['cached_input_supported'],
                'output_cost': cost['output_cost'],
                'provider_fee_cost': cost['provider_fee_cost'],
                'provider_fees': cost.get('provider_fees'),
                'context_threshold_tokens': cost['context_threshold_tokens'],
                'tier_applied': cost.get('tier_applied'),
                'service_tiers': cost['service_tiers'],
                'batch': cost.get('batch'),
                'per_request_cost': cost['total_cost'],
                'workload_cost': round(workload_cost, 6),
                'effective_date': pricing.get('effective_date'),
                'last_verified_date': pricing.get('last_verified_date'),
                'source_url': pricing['source_url'],
                'status': pricing.get('status', 'active'),
                'status_note': pricing.get('status_note'),
                'sunset_date': pricing.get('sunset_date'),
            })

        return {
            'success': True,
            'request_count': request_count,
            'service_tier': service_tier,
            'token_estimate': token_estimate,
            'rows': rows,
            'estimated_at': datetime.utcnow().isoformat()
        }

    def get_pricing_info(self) -> Dict[str, Any]:
        """Get the pricing catalogue and preview-model metadata."""
        return {
            'catalogue_version': self.catalogue.get('catalogue_version'),
            'currency': self.catalogue.get('currency', 'USD'),
            'price_unit': self.catalogue.get('price_unit', 'per_1m_tokens'),
            'records': self.catalogue['records'],
            'preview_model': self.settings.openai_model_name,
            'last_updated': datetime.utcnow().isoformat()
        }

    def validate_pricing_data(self) -> Dict[str, Any]:
        """Validate pricing catalogue completeness."""
        required_fields = [
            'provider', 'provider_name', 'model_id', 'display_name',
            'input_per_million', 'output_per_million',
            'source_url', 'last_verified_date', 'status'
        ]
        invalid_records = []

        for record in self.catalogue['records']:
            missing = [f for f in required_fields if f not in record]
            if missing:
                invalid_records.append({
                    'model_id': record.get('model_id'),
                    'missing_fields': missing
                })

        return {
            'valid': len(invalid_records) == 0,
            'invalid_records': invalid_records,
            'total_models': len(self.catalogue['records'])
        }


# Global pricing manager instance
pricing_manager = PricingManager()
