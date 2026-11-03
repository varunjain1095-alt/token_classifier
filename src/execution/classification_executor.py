"""Full classification execution system for large datasets."""
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import json

from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.providers.openai_provider import openai_provider
from src.results.results_analyzer import results_analyzer
from src.token_module.pricing_manager import pricing_manager

logger = get_logger(__name__)


class ExecutionStatus(Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClassificationExecutor:
    """Executes full classification on large datasets."""
    
    def __init__(self):
        self.executions = {}  # Hot in-memory view; authoritative copy on disk
        self.storage_dir = Path('tmp/executions')
        self.batch_size = 50
        self.max_concurrent_batches = 5
        self.retry_attempts = 3
        self.progress_update_interval = 5  # seconds

    def _persist(self, execution: Dict[str, Any]) -> None:
        """Checkpoint execution state to disk so a restart never loses
        paid classification results. Private keys (`_api_key`) are never
        written."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            serializable = {k: v for k, v in execution.items()
                            if not k.startswith('_')}
            path = self.storage_dir / f"{execution['id']}.json"
            path.write_text(json.dumps(serializable, default=str),
                            encoding='utf-8')
        except Exception as e:
            logger.warning("Failed to persist execution state",
                           execution_id=execution.get('id'), error=str(e))

    def _load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return the execution from memory, or restore it from the on-disk
        checkpoint. A run that was 'running' when the process died is marked
        'paused' so resume can relaunch it from the checkpoint."""
        execution = self.executions.get(execution_id)
        if execution:
            return execution
        path = self.storage_dir / f"{execution_id}.json"
        if not path.exists():
            return None
        try:
            execution = json.loads(path.read_text(encoding='utf-8'))
            if execution.get('status') == ExecutionStatus.RUNNING.value:
                execution['status'] = ExecutionStatus.PAUSED.value
            self.executions[execution_id] = execution
            logger.info("Execution restored from disk",
                        execution_id=execution_id,
                        status=execution.get('status'))
            return execution
        except Exception as e:
            logger.warning("Failed to load execution checkpoint",
                           execution_id=execution_id, error=str(e))
            return None
    
    async def start_execution(self, user_id: str, dataset_records: List[Dict[str, Any]],
                            experiment_config: Dict[str, Any], 
                            category_set: Dict[str, Any],
                            api_key: str,
                            estimated_cost: float) -> Dict[str, Any]:
        """Start full classification execution."""
        try:
            execution_id = str(uuid.uuid4())
            
            # Create execution record
            execution = {
                'id': execution_id,
                'user_id': user_id,
                'created_at': datetime.utcnow().isoformat(),
                'status': ExecutionStatus.PENDING.value,
                'dataset_records': dataset_records,
                'experiment_config': experiment_config,
                'category_set': category_set,
                'estimated_cost': estimated_cost,
                'total_records': len(dataset_records),
                'processed_records': 0,
                'successful_records': 0,
                'failed_records': 0,
                'current_batch': 0,
                'total_batches': (len(dataset_records) + self.batch_size - 1) // self.batch_size,
                'results': [],
                'errors': [],
                'started_at': None,
                'completed_at': None,
                'actual_cost': 0.0,
                'token_usage': {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0
                }
            }
            
            self.executions[execution_id] = execution
            self._persist(execution)

            # Store API key in memory only (not persisted)
            execution['_api_key'] = api_key
            
            logger.info("Classification execution created", 
                       execution_id=execution_id,
                       total_records=len(dataset_records),
                       estimated_cost=estimated_cost,
                       total_batches=execution['total_batches'])
            
            return {
                'success': True,
                'execution_id': execution_id,
                'execution': {k: v for k, v in execution.items() if not k.startswith('_')}
            }
            
        except Exception as e:
            logger.error("Failed to start execution", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def execute_classification(self, execution_id: str) -> Dict[str, Any]:
        """Execute the classification in batches."""
        try:
            execution = self._load(execution_id)
            if not execution:
                return {
                    'success': False,
                    'error': 'Execution not found'
                }

            # Update status
            execution['status'] = ExecutionStatus.RUNNING.value
            if not execution.get('started_at'):
                execution['started_at'] = datetime.utcnow().isoformat()

            api_key = execution['_api_key']
            records = execution['dataset_records']
            config = (execution.get('experiment_config') or {}).get('config', {})

            # Accept a category set ({categories:[...]}), a discovery result
            # ({discovered_categories:[...]}), or a wrapped discovery
            # ({discovery: {discovered_categories:[...]}}).
            category_set = execution.get('category_set') or {}
            if 'discovery' in category_set and isinstance(category_set['discovery'], dict):
                category_set = category_set['discovery']
            categories = (category_set.get('categories')
                          or category_set.get('discovered_categories')
                          or [])

            # Resolve the OpenAI client: a user-supplied key gets a dedicated
            # per-call client; otherwise fall back to the shared/env client.
            if not api_key and not openai_provider.client:
                if not openai_provider.initialize_client():
                    execution['status'] = ExecutionStatus.FAILED.value
                    execution['error'] = 'No OpenAI API key available'
                    return {
                        'success': False,
                        'error': 'No OpenAI API key available'
                    }

            logger.info("Starting classification execution",
                       execution_id=execution_id,
                       total_records=len(records),
                       batch_size=self.batch_size)

            # Process records in batches. On resume, continue from the first
            # unprocessed record rather than re-running finished batches.
            start_batch = execution['processed_records'] // self.batch_size
            for batch_index in range(start_batch, execution['total_batches']):
                if execution['status'] != ExecutionStatus.RUNNING.value:
                    break
                
                start_idx = batch_index * self.batch_size
                end_idx = min(start_idx + self.batch_size, len(records))
                batch_records = records[start_idx:end_idx]
                
                execution['current_batch'] = batch_index + 1
                
                # Process batch
                batch_result = await self._process_batch(
                    batch_records, config, categories, api_key, execution_id
                )
                
                # Update progress
                execution['processed_records'] += len(batch_records)
                execution['successful_records'] += batch_result['successful']
                execution['failed_records'] += batch_result['failed']
                execution['results'].extend(batch_result['results'])
                execution['errors'].extend(batch_result['errors'])
                execution['actual_cost'] += batch_result['cost']
                execution['token_usage']['input_tokens'] += batch_result['token_usage']['input_tokens']
                execution['token_usage']['output_tokens'] += batch_result['token_usage']['output_tokens']
                execution['token_usage']['total_tokens'] += batch_result['token_usage']['total_tokens']
                
                # Progress logging
                progress = (execution['processed_records'] / execution['total_records']) * 100
                logger.info("Batch completed", 
                           execution_id=execution_id,
                           batch=batch_index + 1,
                           total_batches=execution['total_batches'],
                           progress=f"{progress:.1f}%",
                           successful=batch_result['successful'],
                           failed=batch_result['failed'])

                # Checkpoint after every batch — results represent paid API
                # calls and must survive a restart.
                self._persist(execution)

                # Small delay between batches to avoid rate limits
                await asyncio.sleep(0.5)

            # Only mark completed if the run wasn't paused or cancelled
            if execution['status'] == ExecutionStatus.RUNNING.value:
                execution['status'] = ExecutionStatus.COMPLETED.value
                execution['completed_at'] = datetime.utcnow().isoformat()

                # Analyze results (sync analyzer; no expectations for a full
                # run). Adapt executor records to the analyzer's result shape.
                analysis_input = [{
                    'success': True,
                    'record_id': r.get('record_id'),
                    'result': {'classification': r.get('classification')},
                    'usage': r.get('token_usage', {}),
                } for r in execution['results']]
                analysis_input += [{
                    'success': False,
                    'record_id': e.get('record_id'),
                    'error': e.get('error'),
                } for e in execution['errors']]
                execution['final_analysis'] = results_analyzer.analyze_results(
                    analysis_input, []
                )

            self._persist(execution)

            logger.info("Classification execution completed",
                       execution_id=execution_id,
                       status=execution['status'],
                       total_records=execution['total_records'],
                       successful=execution['successful_records'],
                       failed=execution['failed_records'],
                       actual_cost=execution['actual_cost'])
            
            return {
                'success': True,
                'execution': {k: v for k, v in execution.items() if not k.startswith('_')}
            }
            
        except Exception as e:
            if execution := self._load(execution_id):
                execution['status'] = ExecutionStatus.FAILED.value
                execution['error'] = str(e)
                self._persist(execution)
            logger.error("Execution failed", execution_id=execution_id, error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _process_batch(self, batch_records: List[Dict[str, Any]], 
                           config: Dict[str, Any], categories: List[Dict[str, Any]],
                           api_key: str, execution_id: str) -> Dict[str, Any]:
        """Process a batch of records."""
        results = []
        errors = []
        successful = 0
        failed = 0
        total_cost = 0.0
        token_usage = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
        
        # Process records concurrently within batch
        semaphore = asyncio.Semaphore(self.max_concurrent_batches)

        async def process_single_record(record):
            nonlocal successful, failed, total_cost

            async with semaphore:
                try:
                    # Build classification payload
                    payload = self._build_classification_payload(
                        record, config, categories
                    )

                    # Execute classification
                    response = await openai_provider.classify_single(
                        payload,
                        request_id=f"{execution_id}_{record.get('id', 'unknown')}",
                        api_key=api_key
                    )

                    if response['success']:
                        classification = (response.get('result') or {}).get('classification')
                        confidence = (classification.get('confidence')
                                      if isinstance(classification, dict) else None)
                        result = {
                            'record_id': record.get('id', str(uuid.uuid4())),
                            'record': record,
                            'classification': classification,
                            'confidence': confidence,
                            'timestamp': datetime.utcnow().isoformat(),
                            'token_usage': response.get('usage', {})
                        }

                        results.append(result)
                        successful += 1

                        # Update token usage and compute real cost
                        usage = response.get('usage', {})
                        token_usage['input_tokens'] += usage.get('prompt_tokens', 0)
                        token_usage['output_tokens'] += usage.get('completion_tokens', 0)
                        token_usage['total_tokens'] += usage.get('total_tokens', 0)

                        cost = pricing_manager.calculate_cost(
                            response.get('model') or get_settings().openai_model_name,
                            usage.get('prompt_tokens', 0),
                            usage.get('completion_tokens', 0))
                        total_cost += cost.get('total_cost', 0.0)
                        
                    else:
                        errors.append({
                            'record_id': record.get('id', str(uuid.uuid4())),
                            'error': response['error'],
                            'record': record
                        })
                        failed += 1
                        
                except Exception as e:
                    errors.append({
                        'record_id': record.get('id', str(uuid.uuid4())),
                        'error': str(e),
                        'record': record
                    })
                    failed += 1
        
        # Process all records in batch
        tasks = [process_single_record(record) for record in batch_records]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'results': results,
            'errors': errors,
            'successful': successful,
            'failed': failed,
            'cost': total_cost,
            'token_usage': token_usage
        }
    
    def _build_classification_payload(self, record: Dict[str, Any], 
                                    config: Dict[str, Any], 
                                    categories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build classification payload for OpenAI."""
        # Extract text content
        text_content = self._extract_text_content(record)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(config, categories)
        
        # Build user prompt
        user_prompt = self._build_user_prompt(text_content, config, categories)
        
        return {
            'model': config.get('model') or get_settings().openai_model_name,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'max_tokens': config.get('max_tokens', 150),
            'temperature': config.get('temperature', 0.1),
            'response_format': {'type': 'json_object'}
        }
    
    def _extract_text_content(self, record: Dict[str, Any]) -> str:
        """Extract text content from record."""
        # Look for common text fields
        text_fields = ['original_review_text', 'review_text', 'text', 'content', 'review', 'comment', 'feedback']
        
        for field in text_fields:
            if field in record and record[field]:
                return str(record[field])
        
        # Fallback to any string field
        for key, value in record.items():
            if isinstance(value, str) and len(value) > 10:
                return value
        
        return str(record)
    
    def _build_system_prompt(self, config: Dict[str, Any], 
                           categories: List[Dict[str, Any]]) -> str:
        """Build system prompt for classification."""
        prompt = "You are an AI assistant that classifies review content into predefined categories."
        
        if categories:
            category_descriptions = []
            for cat in categories:
                desc = f"- {cat['name']}"
                if cat.get('description'):
                    desc += f": {cat['description']}"
                category_descriptions.append(desc)
            
            prompt += f"\n\nAvailable categories:\n" + "\n".join(category_descriptions)
        
        prompt += "\n\nRespond with a JSON object containing:"
        prompt += "\n- 'category': The most appropriate category name"
        prompt += "\n- 'confidence': Your confidence score (0.0-1.0)"
        prompt += "\n- 'reasoning': Brief explanation of your choice"
        
        return prompt
    
    def _build_user_prompt(self, text_content: str, 
                          config: Dict[str, Any], 
                          categories: List[Dict[str, Any]]) -> str:
        """Build user prompt for classification."""
        prompt = f"Please classify the following review text:\n\n{text_content}"
        
        if categories:
            prompt += "\n\nAvailable categories:"
            for cat in categories:
                prompt += f"\n- {cat['name']}"
        
        prompt += "\n\nReturn your classification as JSON."
        
        return prompt
    
    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status."""
        execution = self._load(execution_id)
        if not execution:
            return {'error': 'Execution not found'}
        
        return {
            'id': execution_id,
            'execution_id': execution_id,
            'status': execution['status'],
            'progress': (execution['processed_records'] / execution['total_records']) * 100,
            'processed_records': execution['processed_records'],
            'total_records': execution['total_records'],
            'successful_records': execution['successful_records'],
            'failed_records': execution['failed_records'],
            'current_batch': execution['current_batch'],
            'total_batches': execution['total_batches'],
            'estimated_cost': execution['estimated_cost'],
            'actual_cost': execution['actual_cost'],
            'token_usage': execution['token_usage'],
            'created_at': execution['created_at'],
            'started_at': execution['started_at'],
            'completed_at': execution['completed_at'],
            'errors_count': len(execution['errors'])
        }
    
    def pause_execution(self, execution_id: str) -> Dict[str, Any]:
        """Pause execution."""
        execution = self._load(execution_id)
        if not execution:
            return {'error': 'Execution not found'}

        if execution['status'] == ExecutionStatus.RUNNING.value:
            execution['status'] = ExecutionStatus.PAUSED.value
            self._persist(execution)
            logger.info("Execution paused", execution_id=execution_id)
            return {'success': True, 'status': 'paused'}
        else:
            return {'error': 'Cannot pause execution in current state'}

    def resume_execution(self, execution_id: str) -> Dict[str, Any]:
        """Resume execution."""
        execution = self._load(execution_id)
        if not execution:
            return {'error': 'Execution not found'}

        if execution['status'] == ExecutionStatus.PAUSED.value:
            execution['status'] = ExecutionStatus.RUNNING.value
            self._persist(execution)
            logger.info("Execution resumed", execution_id=execution_id)
            return {'success': True, 'status': 'resumed'}
        else:
            return {'error': 'Cannot resume execution in current state'}

    def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """Cancel execution."""
        execution = self._load(execution_id)
        if not execution:
            return {'error': 'Execution not found'}

        execution['status'] = ExecutionStatus.CANCELLED.value
        execution['completed_at'] = datetime.utcnow().isoformat()
        self._persist(execution)
        logger.info("Execution cancelled", execution_id=execution_id)
        return {'success': True, 'status': 'cancelled'}

    def get_execution_results(self, execution_id: str) -> Dict[str, Any]:
        """Get execution results."""
        execution = self._load(execution_id)
        if not execution:
            return {'error': 'Execution not found'}
        
        return {
            'execution_id': execution_id,
            'results': execution['results'],
            'errors': execution['errors'],
            'final_analysis': execution.get('final_analysis'),
            'summary': {
                'total_processed': execution['processed_records'],
                'successful': execution['successful_records'],
                'failed': execution['failed_records'],
                'success_rate': (execution['successful_records'] / max(execution['processed_records'], 1)) * 100,
                'actual_cost': execution['actual_cost'],
                'token_usage': execution['token_usage']
            }
        }
    
    def get_user_executions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all executions for user."""
        # Restore on-disk checkpoints for executions not currently in memory
        if self.storage_dir.exists():
            for path in self.storage_dir.glob('*.json'):
                if path.stem not in self.executions:
                    self._load(path.stem)

        user_executions = []
        for execution in self.executions.values():
            if execution['user_id'] == user_id:
                user_executions.append({
                    'id': execution['id'],
                    'created_at': execution['created_at'],
                    'status': execution['status'],
                    'total_records': execution['total_records'],
                    'processed_records': execution['processed_records'],
                    'successful_records': execution['successful_records'],
                    'estimated_cost': execution['estimated_cost'],
                    'actual_cost': execution['actual_cost']
                })
        
        # Sort by creation date (newest first)
        user_executions.sort(key=lambda x: x['created_at'], reverse=True)
        return user_executions


# Global classification executor instance
classification_executor = ClassificationExecutor()
