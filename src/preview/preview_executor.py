"""Preview execution for classification testing."""
import uuid
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.providers.openai_provider import openai_provider, ProviderStatus
from src.token_module.recalibration_contract import recalibration_contract
from src.token_module.token_counter import token_counter
from src.configuration.experiment_manager import experiment_manager
from src.token_module.pricing_manager import pricing_manager
from src.preview.reliability import (
    build_run_fingerprint, assess_run, compare_runs)

logger = get_logger(__name__)

settings = get_settings()

# First-class fallback label: always present in a discovered taxonomy so the
# model has an explicit escape hatch and diagnostics can treat it as a known
# member rather than drift.
UNMATCHED_LABEL = 'other'


class PreviewStatus(Enum):
    """Preview execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    QUOTA_EXCEEDED = "quota_exceeded"


class PreviewExecutor:
    """Executes classification previews with quota management."""
    
    def __init__(self):
        self.previews = {}  # In-memory storage for now
        self.quota_limits = {
            'anonymous': {'requests_per_hour': 10, 'requests_per_day': 50},
            'signed_in': {'requests_per_hour': 100, 'requests_per_day': 1000}
        }
    
    async def execute_preview(self, sample_records: List[Dict[str, Any]], 
                            experiment_config: Dict[str, Any],
                            expectations: List[Dict[str, Any]],
                            user_id: str,
                            api_key: str = None,
                            regenerate_taxonomy: bool = False,
                            stability_run: bool = False) -> Dict[str, Any]:
        """Execute classification preview."""
        try:
            preview_id = str(uuid.uuid4())

            # A user-supplied key is used per-call (dedicated client), never
            # stored on the shared provider. With no key, ensure the shared
            # env-key client exists.
            if not api_key and not openai_provider.client:
                if not openai_provider.initialize_client():
                    return {
                        'success': False,
                        'error': 'OpenAI client not initialized and no API key provided',
                        'status': PreviewStatus.FAILED.value
                    }
            
            # Create preview record
            preview = {
                'id': preview_id,
                'sample_records': sample_records,
                'experiment_config': experiment_config,
                'expectations': expectations,
                'user_id': user_id,
                'status': PreviewStatus.RUNNING.value,
                'created_at': datetime.utcnow().isoformat(),
                'results': [],
                'provider_status': None,
                'quota_info': {}
            }
            
            self.previews[preview_id] = preview
            
            # Execute classifications
            results = await self._execute_classifications(
                sample_records, experiment_config, preview_id,
                regenerate_taxonomy=regenerate_taxonomy,
                stability_run=stability_run,
                api_key=api_key)

            # Derive status from per-record outcomes: all failed → FAILED,
            # some failed → PARTIAL, all succeeded → COMPLETED.
            summary = results.get('summary', {})
            successful = summary.get('successful', 0)
            total = summary.get('total', len(sample_records))

            preview['results'] = results
            preview['taxonomy'] = results.get('taxonomy')
            preview['run_fingerprint'] = results.get('run_fingerprint')
            preview['diagnostics'] = results.get('diagnostics')
            preview['provider_status'] = results.get('provider_status')
            preview['completed_at'] = datetime.utcnow().isoformat()
            # Only previews with at least one successful classification
            # consume the free-preview quota.
            preview['billable'] = successful > 0

            if not results.get('success') or successful == 0:
                preview['status'] = PreviewStatus.FAILED.value
            elif successful < total:
                preview['status'] = PreviewStatus.PARTIAL.value
            else:
                preview['status'] = PreviewStatus.COMPLETED.value

            # Record usage for recalibration only when something succeeded
            if successful > 0:
                self._record_usage_for_recalibration(
                    results['results'], preview_id,
                    results.get('payloads', []))
            results.pop('payloads', None)

            logger.info("Preview execution completed",
                       preview_id=preview_id,
                       status=preview['status'],
                       successful=successful)

            if preview['status'] == PreviewStatus.FAILED.value:
                # Surface the actual API error instead of a generic failure
                first_error = results.get('error') or next(
                    (r.get('error') for r in results.get('results', [])
                     if isinstance(r, dict) and r.get('error')),
                    'All classifications failed'
                )
                return {
                    'success': False,
                    'error': first_error,
                    'preview_id': preview_id,
                    'status': preview['status'],
                    'results': results,
                    'preview': preview
                }

            return {
                'success': True,
                'preview_id': preview_id,
                'status': preview['status'],
                'results': results,
                'preview': preview
            }
            
        except Exception as e:
            logger.error("Preview execution failed", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'status': PreviewStatus.FAILED.value
            }
    
    async def _execute_classifications(self, sample_records: List[Dict[str, Any]],
                                     experiment_config: Dict[str, Any],
                                     preview_id: str,
                                     regenerate_taxonomy: bool = False,
                                     stability_run: bool = False,
                                     api_key: str = None) -> Dict[str, Any]:
        """Execute classifications for sample records."""
        try:
            config = experiment_config.get('config', {})
            discovery_mode = (
                config.get('classification_type') == 'undefined'
                or config.get('category_mode') == 'discovery'
            )

            # In discovery mode, classify every record against the shared draft
            # taxonomy stored on the configuration. It is generated once and
            # reused on reruns; a new version is only created when the caller
            # explicitly requests regeneration.
            taxonomy = []
            themes = []
            taxonomy_obj = None
            if discovery_mode:
                taxonomy_obj = await self._resolve_taxonomy(
                    sample_records, experiment_config, regenerate_taxonomy, api_key)
                taxonomy = taxonomy_obj.get('labels', [])
                themes = taxonomy_obj.get('themes') or taxonomy

            # Build request payloads
            payloads = []
            for i, record in enumerate(sample_records):
                payload = self._build_classification_payload(
                    record, experiment_config, themes
                )
                payloads.append(payload)

            # Execute batch classification
            batch_id = f"preview_{preview_id}"
            results = await openai_provider.classify_batch(
                payloads, batch_id, api_key=api_key)
            results['payloads'] = payloads
            if taxonomy_obj is not None:
                results['taxonomy'] = taxonomy_obj
                unassigned = self._unassigned_guidance_themes(
                    taxonomy_obj, results.get('results', []))
                if unassigned:
                    results['unassigned_guidance_themes'] = unassigned

            # Add record IDs to results
            for i, result in enumerate(results.get('results', [])):
                if i < len(sample_records):
                    result['record_id'] = sample_records[i].get('id', f'record_{i}')
                    result['record_index'] = i

            # Reliability layer: fingerprint this run and assess the raw
            # results without modifying them.
            results['run_fingerprint'] = build_run_fingerprint(
                sample_records, config, taxonomy_obj, settings.openai_model_name)
            results['diagnostics'] = assess_run(
                results.get('results', []), sample_records, config, taxonomy_obj)

            # Batched consistency diagnostic: a single model call assesses
            # whether each category is supported by its evidence. The raw
            # classifications are never modified.
            consistency, diag_usage = await self._assess_consistency(
                sample_records, results.get('results', []), taxonomy, api_key)
            if consistency:
                results['consistency'] = consistency
            if diag_usage:
                cost = pricing_manager.calculate_cost(
                    settings.openai_model_name,
                    input_tokens=diag_usage.get('prompt_tokens', 0),
                    output_tokens=diag_usage.get('completion_tokens', 0))
                results['diagnostic_usage'] = {
                    'prompt_tokens': diag_usage.get('prompt_tokens', 0),
                    'completion_tokens': diag_usage.get('completion_tokens', 0),
                    'total_tokens': diag_usage.get('total_tokens', 0),
                    'cost_usd': cost.get('total_cost', 0.0),
                    'model': settings.openai_model_name,
                }

            # Optional stability pass: repeat the identical batch and compare
            # raw labels. Does not change the primary results.
            if stability_run:
                rerun = await openai_provider.classify_batch(
                    payloads, f"{batch_id}_stability", api_key=api_key)
                for i, result in enumerate(rerun.get('results', [])):
                    if i < len(sample_records):
                        result['record_id'] = sample_records[i].get(
                            'id', f'record_{i}')
                results['stability'] = compare_runs(
                    results.get('results', []), rerun.get('results', []))
                logger.info("Stability run completed",
                            preview_id=preview_id,
                            changed=results['stability'].get('changed'))

            return results
            
        except Exception as e:
            logger.error("Classification execution failed", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'provider_status': ProviderStatus.ERROR.value
            }
    
    async def _assess_consistency(self, sample_records: List[Dict[str, Any]],
                                  results: List[Dict[str, Any]],
                                  taxonomy_labels: List[str],
                                  api_key: str = None) -> tuple:
        """One batched diagnostic call: for every result decide whether the
        category is supported by its evidence. Returns (assessments, usage).
        Read-only with respect to the classifications."""
        texts = {r.get('id'): str(r.get('review_text', '')) for r in sample_records}
        items = []
        for r in results:
            if not r.get('success'):
                continue
            cls = (r.get('result') or {}).get('classification')
            if not isinstance(cls, dict):
                continue
            rid = r.get('record_id')
            items.append({
                'record_id': rid,
                'category': cls.get('primary_category'),
                'evidence': cls.get('supporting_evidence'),
                'classification_state': cls.get('classification_state'),
                'review_text': texts.get(rid, '')[:500],
            })
        if not items:
            return [], None

        system = (
            'You audit review classifications for category-evidence consistency.\n'
            'For each item decide whether the category is SUPPORTED by the quoted '
            'evidence and review text.\n'
            'Verdicts: "supported" (evidence clearly justifies the category), '
            '"questionable" (partial or weak fit), "unsupported" (evidence does '
            'not justify the category).\n'
            'Respond with JSON: {"assessments": [{"record_id": "...", '
            '"verdict": "supported|questionable|unsupported", '
            '"reason": "<one short sentence>"}]}')
        if taxonomy_labels:
            system += ('\nShared taxonomy labels for context: '
                       + ', '.join(taxonomy_labels))

        payload = {
            'model': settings.openai_model_name,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': json.dumps(items)},
            ],
            'max_tokens': 1200,
            'temperature': 0.0,
            'response_format': {'type': 'json_object'},
        }

        try:
            response = await openai_provider.classify_single(
                payload, request_id='consistency_check', api_key=api_key)
            classification = (response.get('result') or {}).get('classification')
            if isinstance(classification, str):
                try:
                    classification = json.loads(classification)
                except Exception:
                    classification = {}
            assessments = (classification or {}).get('assessments', [])
            usage = (response.get('usage') or {})
            logger.info("Consistency check completed",
                        assessed=len(assessments),
                        tokens=usage.get('total_tokens'))
            return assessments, usage
        except Exception as e:
            logger.error("Consistency check failed", error=str(e))
            return [], None

    async def _resolve_taxonomy(self, sample_records: List[Dict[str, Any]],
                                experiment_config: Dict[str, Any],
                                regenerate: bool = False,
                                api_key: str = None) -> Dict[str, Any]:
        """Return the configuration's stored draft taxonomy.

        The taxonomy is discovered once and persisted on the configuration
        (with an id + version), so rerunning the same sample/configuration
        reuses it. A new version is generated only when `regenerate` is set.
        """
        config = experiment_config.get('config', {})
        config_id = experiment_config.get('id')
        existing = config.get('draft_taxonomy')

        # The request may carry a stale config object — recover the taxonomy
        # from the stored configuration by id.
        if not existing and config_id:
            stored = experiment_manager.get_experiment_config(config_id)
            if stored:
                existing = stored.get('config', {}).get('draft_taxonomy')
                if existing:
                    config['draft_taxonomy'] = existing

        if existing and not regenerate:
            warning = self._taxonomy_sample_warning(existing, sample_records)
            if warning:
                logger.warning("Reused taxonomy was built from a different sample",
                               taxonomy_id=existing.get('id'),
                               overlap_ratio=warning['overlap_ratio'])
                return {**existing, 'sample_mismatch': warning}
            logger.info("Reusing stored draft taxonomy",
                        taxonomy_id=existing.get('id'),
                        version=existing.get('version'))
            return existing

        themes = await self._discover_taxonomy(sample_records, config, api_key)
        labels = [t['label'] for t in themes]
        if UNMATCHED_LABEL not in {l.lower() for l in labels}:
            labels.append(UNMATCHED_LABEL)
            themes.append({
                'label': UNMATCHED_LABEL,
                'description': 'use only when no taxonomy theme fits',
                'from_guidance': False,
            })
        taxonomy = {
            'id': str(uuid.uuid4()),
            'version': (existing or {}).get('version', 0) + 1,
            'objective': config.get('objective'),
            'sample_record_ids': [r.get('id') for r in sample_records],
            'labels': labels,
            'themes': themes,
            'unmatched_label': UNMATCHED_LABEL,
            'created_at': datetime.utcnow().isoformat()
        }
        config['draft_taxonomy'] = taxonomy
        if config_id:
            experiment_manager.set_draft_taxonomy(config_id, taxonomy)
        logger.info("Draft taxonomy discovered",
                    taxonomy_id=taxonomy['id'],
                    version=taxonomy['version'],
                    themes=len(labels))
        return taxonomy

    def _unassigned_guidance_themes(self, taxonomy: Dict[str, Any],
                                    results: List[Dict[str, Any]]) -> List[str]:
        """Flag user-suggested themes that no record was assigned to — a sign
        the guidance does not match the data (read-only diagnostic)."""
        themes = taxonomy.get('themes') or []
        guidance_labels = [t.get('label') for t in themes
                           if isinstance(t, dict) and t.get('from_guidance')]
        if not guidance_labels:
            return []
        assigned = set()
        for r in results:
            if not r.get('success'):
                continue
            cls = (r.get('result') or {}).get('classification')
            if isinstance(cls, dict):
                assigned.add(cls.get('primary_category'))
        return [l for l in guidance_labels if l not in assigned]

    def _taxonomy_sample_warning(self, taxonomy: Dict[str, Any],
                                 sample_records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Flag when a reused taxonomy was discovered on a materially
        different sample than the one being classified now."""
        stored_ids = set(taxonomy.get('sample_record_ids') or [])
        current_ids = {r.get('id') for r in sample_records if r.get('id')}
        if not stored_ids or not current_ids:
            return None
        overlap = len(stored_ids & current_ids)
        ratio = overlap / len(current_ids)
        if ratio >= 0.5:
            return None
        return {
            'warning': 'taxonomy_sample_mismatch',
            'message': 'This taxonomy was discovered on a different sample; '
                       'consider regenerating it.',
            'overlap_ratio': round(ratio, 2),
            'stored_sample_size': len(stored_ids),
            'current_sample_size': len(current_ids),
        }

    async def _discover_taxonomy(self, sample_records: List[Dict[str, Any]],
                                 config: Dict[str, Any],
                                 api_key: str = None) -> List[Dict[str, Any]]:
        """Discover a shared draft taxonomy of topical themes across the sample.

        Returns a list of {"label", "description", "from_guidance"} objects."""
        objective = config.get('objective') or 'Identify the main themes in these reviews'
        theme_guidance = config.get('theme_guidance')

        lines = [
            'You are building a draft taxonomy of topical themes for review classification.',
            f'Objective: {objective}',
            '',
            'Analyse ALL of the reviews below and propose a small set of concise, distinct, '
            'reusable topical theme labels (5-12) that cover the recurring subjects — for '
            'example "Search/retrieval difficulty", "Query refinement", "Navigation", '
            '"Missing features", "User behaviour".',
            'Do NOT propose sentiment labels (e.g. Positive/Negative/Neutral) unless the '
            'objective explicitly asks for sentiment analysis.',
        ]
        if theme_guidance:
            lines.append(
                f'The user suggested these possible themes: {theme_guidance}. '
                'Include a suggested theme ONLY if the reviews actually support it; '
                'drop suggestions with no support in the data. You may also propose '
                'themes the user did not suggest when the data clearly supports them.')
        lines.append('')
        lines.append('Respond with JSON: {"themes": [{"label": "<short label>", '
                     '"description": "<one phrase describing what fits this theme>", '
                     '"from_guidance": true|false}]}')

        review_lines = []
        total_chars = 0
        for i, r in enumerate(sample_records):
            text = str(r.get('review_text', ''))[:500]
            if not text.strip():
                continue
            entry = f'{i + 1}. {text}'
            if total_chars + len(entry) > 20000:
                break
            total_chars += len(entry)
            review_lines.append(entry)

        payload = {
            'model': settings.openai_model_name,
            'messages': [
                {'role': 'system', 'content': '\n'.join(lines)},
                {'role': 'user', 'content': '\n\n'.join(review_lines)},
            ],
            'max_tokens': 500,
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
        }

        try:
            response = await openai_provider.classify_single(
                payload, request_id='taxonomy_discovery', api_key=api_key
            )
            classification = (response.get('result') or {}).get('classification')
            if isinstance(classification, str):
                import json
                try:
                    classification = json.loads(classification)
                except Exception:
                    classification = {}
            raw_themes = (classification or {}).get('themes', [])
            themes = []
            for t in raw_themes:
                if isinstance(t, dict):
                    label = str(t.get('label') or '').strip()
                    if not label or label.lower() == UNMATCHED_LABEL:
                        continue
                    themes.append({
                        'label': label,
                        'description': str(t.get('description') or '').strip(),
                        'from_guidance': bool(t.get('from_guidance')),
                    })
                else:
                    label = str(t).strip()
                    if label and label.lower() != UNMATCHED_LABEL:
                        themes.append({'label': label, 'description': '',
                                       'from_guidance': False})
            return themes
        except Exception as e:
            logger.error("Taxonomy discovery failed", error=str(e))
            return []

    def _build_classification_payload(self, record: Dict[str, Any],
                                    experiment_config: Dict[str, Any],
                                    taxonomy: List[Any] = None) -> Dict[str, Any]:
        """Build OpenAI request payload for a record."""
        config = experiment_config.get('config', {})
        classification_type = config.get('classification_type', 'sentiment')

        # Build messages based on classification type
        messages = self._build_messages(record, config, classification_type, taxonomy)
        
        payload = {
            'model': settings.openai_model_name,
            'messages': messages,
            'max_tokens': config.get('max_tokens', 150),
            'temperature': config.get('temperature', 0.1),
            'response_format': {'type': 'json_object' if config.get('output_format') == 'json' else 'text'}
        }
        
        return payload
    
    def _build_messages(self, record: Dict[str, Any],
                       config: Dict[str, Any],
                       classification_type: str,
                       taxonomy: List[Any] = None) -> List[Dict[str, str]]:
        """Build OpenAI messages for classification."""
        review_text = record.get('review_text', '')
        system_prompt = config.get('system_prompt', '')
        
        if not system_prompt:
            # Build default system prompt based on classification type
            if classification_type == 'undefined' or config.get('category_mode') == 'discovery':
                system_prompt = self._build_discovery_prompt(config, taxonomy)
            elif classification_type == 'sentiment':
                system_prompt = "Classify the sentiment of the following review as positive, negative, or neutral. Respond with JSON containing 'sentiment' and 'confidence' fields."
            elif classification_type == 'topic':
                system_prompt = "Classify the main topic of the following review. Respond with JSON containing 'topic' and 'confidence' fields."
            elif classification_type == 'category':
                system_prompt = "Classify the following review into the appropriate category. Respond with JSON containing 'category' and 'confidence' fields."
            else:
                system_prompt = "Classify the following review. Respond with JSON containing your classification and confidence."
        
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': review_text}
        ]

        return messages

    def _build_discovery_prompt(self, config: Dict[str, Any],
                                taxonomy: List[Any] = None) -> str:
        """Build a theme-discovery classification prompt honoring the saved
        objective, label mode, requested output fields and shared taxonomy."""
        objective = config.get('objective') or 'Identify the main themes in these reviews'
        label_mode = config.get('label_mode', 'single_label')
        output_fields = config.get('output_fields') or ['primary_category']

        lines = [
            'You are classifying reviews into a shared taxonomy of topical themes.',
            f'Classification objective: {objective}',
            '',
        ]

        if taxonomy:
            lines.append('Allowed taxonomy labels (reuse these exactly):')
            for item in taxonomy:
                if isinstance(item, dict):
                    label = item.get('label', '')
                    desc = item.get('description') or ''
                    lines.append(f'- {label}' + (f' — {desc}' if desc else ''))
                else:
                    lines.append(f'- {item}')
            lines.append('')
            fallback = (f'If no theme fits, set primary_category to "{UNMATCHED_LABEL}"'
                        + (' and classification_state to "unmatched".'
                           if 'classification_state' in output_fields else '.'))
            lines.append('Choose the primary_category ONLY from the taxonomy above. '
                         + fallback)
        else:
            lines.append('Assign a concise, reusable topical theme label '
                         '(e.g. "Search/retrieval difficulty", "Missing features").')

        lines.append('The label MUST be a topical category relevant to the objective. '
                     'Sentiment labels such as Positive/Negative/Neutral are NOT valid '
                     'unless the objective explicitly asks for sentiment analysis.')

        # Raw theme_guidance is intentionally NOT injected here: the taxonomy
        # shown above is already the data-filtered distillation of it. Pushing
        # user-suggested themes into per-record prompts biases the model toward
        # forcing records into themes the data may not support.

        if label_mode == 'multi_label':
            lines.append('Label mode: multi-label — primary_category from the taxonomy, '
                         'plus secondary_categories drawn from the same taxonomy when relevant.')
        else:
            lines.append('Label mode: single-label — assign exactly one primary_category.')

        field_instructions = {
            'primary_category': '"primary_category": the single main theme label (short noun phrase)',
            'secondary_categories': '"secondary_categories": array of additional theme labels (empty if none)',
            'supporting_evidence': '"supporting_evidence": a short verbatim quote from the review that supports the label',
            'classification_state': '"classification_state": one of "matched" (clear theme applies), "unmatched" (no theme applies), "ambiguous" (multiple competing themes)',
            'confidence': '"confidence": one of "high", "medium", "low"',
            'explanation': '"explanation": one sentence explaining the chosen label',
        }

        requested = [
            field_instructions[f] for f in
            ['primary_category', 'secondary_categories', 'supporting_evidence',
             'classification_state', 'confidence', 'explanation']
            if f == 'primary_category' or f in output_fields
        ]
        lines.append('')
        lines.append('Respond with a JSON object containing exactly these fields:')
        lines.extend(f'- {r}' for r in requested)

        return '\n'.join(lines)
    
    def _record_usage_for_recalibration(self, results: List[Dict[str, Any]],
                                        preview_id: str,
                                        payloads: List[Dict[str, Any]] = None):
        """Record estimate-vs-actual token usage for recalibration."""
        try:
            for i, result in enumerate(results):
                if result.get('success') and 'usage' in result:
                    usage = result['usage']
                    actual_tokens = {
                        'input_tokens': usage.get('prompt_tokens', 0),
                        'output_tokens': usage.get('completion_tokens', 0),
                        'total_tokens': usage.get('total_tokens', 0)
                    }

                    # Estimate the same payload with tiktoken so calibration
                    # compares estimate vs actual (not actual vs actual).
                    if payloads and i < len(payloads):
                        estimated_tokens = token_counter.estimate_request_tokens(
                            payloads[i])
                    else:
                        estimated_tokens = actual_tokens

                    recalibration_contract.add_actual_usage(
                        request_id=result.get('record_id', 'unknown'),
                        estimated_tokens=estimated_tokens,
                        actual_tokens=actual_tokens,
                        model=result.get('model', settings.openai_model_name)
                    )
                    
        except Exception as e:
            logger.error("Failed to record usage for recalibration", error=str(e))
    
    def get_preview(self, preview_id: str) -> Optional[Dict[str, Any]]:
        """Get preview by ID."""
        return self.previews.get(preview_id)
    
    def get_user_previews(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all previews for a user."""
        return [
            preview for preview in self.previews.values()
            if preview['user_id'] == user_id
        ]
    
    def check_quota(self, user_id: str, user_type: str = 'anonymous') -> Dict[str, Any]:
        """Check user quota for preview requests."""
        try:
            limits = self.quota_limits.get(user_type, self.quota_limits['anonymous'])

            # Only billable previews (>= 1 successful classification) count
            # against the quota — fully failed runs are free.
            user_previews = [
                p for p in self.get_user_previews(user_id)
                if p.get('billable', True)
            ]
            now = datetime.utcnow()
            
            # Count requests in last hour and day
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(days=1)
            
            hourly_count = len([
                p for p in user_previews 
                if datetime.fromisoformat(p['created_at']) > hour_ago
            ])
            
            daily_count = len([
                p for p in user_previews 
                if datetime.fromisoformat(p['created_at']) > day_ago
            ])
            
            # Check limits
            hourly_exceeded = hourly_count >= limits['requests_per_hour']
            daily_exceeded = daily_count >= limits['requests_per_day']
            
            quota_info = {
                'user_type': user_type,
                'limits': limits,
                'usage': {
                    'hourly': hourly_count,
                    'daily': daily_count
                },
                'exceeded': {
                    'hourly': hourly_exceeded,
                    'daily': daily_exceeded,
                    'any': hourly_exceeded or daily_exceeded
                },
                'remaining': {
                    'hourly': max(0, limits['requests_per_hour'] - hourly_count),
                    'daily': max(0, limits['requests_per_day'] - daily_count)
                }
            }
            
            return quota_info
            
        except Exception as e:
            logger.error("Quota check failed", error=str(e))
            return {
                'user_type': user_type,
                'error': str(e),
                'exceeded': {'any': True}
            }
    
    def get_preview_summary(self, preview_id: str) -> Dict[str, Any]:
        """Get preview summary with results analysis."""
        preview = self.get_preview(preview_id)
        if not preview:
            return {'error': 'Preview not found'}
        
        results = preview.get('results', {}).get('results', [])
        expectations = preview.get('expectations', [])
        
        # Analyze results vs expectations
        analysis = self._analyze_results_vs_expectations(results, expectations)
        
        return {
            'preview_id': preview_id,
            'status': preview['status'],
            'taxonomy': preview.get('taxonomy'),
            'run_fingerprint': preview.get('run_fingerprint'),
            'diagnostics': preview.get('diagnostics'),
            'stability': preview.get('results', {}).get('stability'),
            'consistency': preview.get('results', {}).get('consistency'),
            'diagnostic_usage': preview.get('results', {}).get('diagnostic_usage'),
            'created_at': preview['created_at'],
            'completed_at': preview.get('completed_at'),
            'summary': {
                'total_records': len(preview.get('sample_records', [])),
                'successful_classifications': len([r for r in results if r.get('success')]),
                'failed_classifications': len([r for r in results if not r.get('success')]),
                'expectations_count': len(expectations)
            },
            'analysis': analysis
        }
    
    def _analyze_results_vs_expectations(self, results: List[Dict[str, Any]], 
                                       expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze classification results vs user expectations."""
        try:
            # Create lookup for expectations by record_id
            expectation_lookup = {exp['record_id']: exp for exp in expectations}
            
            matches = 0
            mismatches = 0
            no_expectation = 0
            
            detailed_results = []
            
            for result in results:
                record_id = result.get('record_id')
                expectation = expectation_lookup.get(record_id)
                
                if not expectation:
                    no_expectation += 1
                    detailed_results.append({
                        'record_id': record_id,
                        'result': result,
                        'expectation': None,
                        'match': None
                    })
                    continue
                
                # Compare result with expectation
                expected_value = expectation.get('expected_value', '')
                actual_result = result.get('result', {}).get('classification', '')
                
                # Simple matching logic - can be enhanced
                match = self._compare_results(actual_result, expected_value)
                
                if match:
                    matches += 1
                else:
                    mismatches += 1
                
                detailed_results.append({
                    'record_id': record_id,
                    'result': result,
                    'expectation': expectation,
                    'match': match,
                    'expected': expected_value,
                    'actual': actual_result
                })
            
            total_comparable = matches + mismatches
            evaluated = total_comparable > 0
            accuracy = (matches / total_comparable) * 100 if evaluated else None

            return {
                'evaluated': evaluated,
                'total_results': len(results),
                'total_expectations': len(expectations),
                'comparable_results': total_comparable,
                'matches': matches,
                'mismatches': mismatches,
                'no_expectation': no_expectation,
                'accuracy_percentage': round(accuracy, 2) if accuracy is not None else None,
                'detailed_results': detailed_results
            }
            
        except Exception as e:
            logger.error("Failed to analyze results vs expectations", error=str(e))
            return {'error': str(e)}
    
    def _compare_results(self, actual: Any, expected: str) -> bool:
        """Compare actual result with expected value."""
        try:
            # Handle different result formats
            if isinstance(actual, dict):
                # Look for common fields
                for field in ['sentiment', 'category', 'topic', 'classification']:
                    if field in actual:
                        actual_value = str(actual[field]).lower()
                        expected_value = str(expected).lower()
                        return actual_value == expected_value or expected_value in actual_value
                
                # If no common field, convert to string
                actual = str(actual)
            
            # Simple string comparison
            actual_str = str(actual).lower()
            expected_str = str(expected).lower()
            
            return actual_str == expected_str or expected_str in actual_str
            
        except Exception as e:
            logger.error("Failed to compare results", error=str(e))
            return False


# Global preview executor instance
preview_executor = PreviewExecutor()
